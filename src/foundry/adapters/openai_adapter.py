"""OpenAI streaming adapter that emits canonical Foundry events."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections import deque
from collections.abc import AsyncIterator as AsyncIteratorABC, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from itertools import count
from typing import Any, AsyncIterator, Callable, Deque

from foundry.core.adapters.toolbridge import ToolSpec, tool_specs_to_openai

from .base import (
    AdapterStreamError,
    BaseAdapter,
    BaseEvent,
    FinalEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)

__all__ = ["OpenAIAdapter", "monotonic_seq", "stable_ts", "TS_ORIGIN", "TS_STEP"]

TS_ORIGIN = datetime(2024, 1, 1, tzinfo=timezone.utc)
TS_STEP = timedelta(milliseconds=1)


def monotonic_seq(*, start: int = 0) -> Callable[[], int]:
    """Return a callable that yields strictly increasing integers."""

    counter = count(start)

    def _next() -> int:
        return next(counter)

    return _next


def stable_ts(*, origin: datetime = TS_ORIGIN, step: timedelta = TS_STEP) -> Callable[[], datetime]:
    """Return a callable that yields deterministic timestamps."""

    counter = count()

    def _next() -> datetime:
        index = next(counter)
        return origin + step * index

    return _next


class OpenAIAdapter(BaseAdapter):
    """Translate prompts into OpenAI streaming responses."""

    def __init__(
        self,
        client: Any,
        *,
        default_model: str | None = None,
        default_params: Mapping[str, Any] | None = None,
        stream_factory: Callable[[Any, Mapping[str, Any]], Any] | None = None,
    ) -> None:
        self._client = client
        self._default_model = default_model
        self._default_params = dict(default_params or {})
        self._stream_factory = stream_factory or _default_stream_factory

        if "model" in self._default_params and self._default_model is None:
            model_value = self._default_params.pop("model")
            self._default_model = str(model_value)

        reserved = {"messages", "stream"}
        conflict = reserved.intersection(self._default_params)
        if conflict:
            joined = ", ".join(sorted(conflict))
            msg = f"default parameters cannot include reserved keys: {joined}"
            raise ValueError(msg)

    def stream(self, prompt: str, /, **kwargs: Any) -> AsyncIterator[BaseEvent]:
        if not isinstance(prompt, str) or not prompt:
            msg = "prompt must be a non-empty string"
            raise AdapterStreamError(msg)

        system_prompt = kwargs.pop("system_prompt", None)
        if system_prompt is not None and not isinstance(system_prompt, str):
            msg = "system_prompt must be a string when provided"
            raise AdapterStreamError(msg)

        tools = kwargs.pop("tools", None)
        prepared_tools = self._prepare_tools(tools)

        payload = self._build_payload(
            prompt,
            system_prompt=system_prompt,
            tools=prepared_tools,
            extra_options=kwargs,
        )

        try:
            stream = self._stream_factory(self._client, payload)
        except Exception as exc:  # pragma: no cover - defensive guard
            msg = "OpenAI client call failed"
            raise AdapterStreamError(msg) from exc

        normalizer = _OpenAINormalizer(
            seq_factory=monotonic_seq(),
            ts_factory=stable_ts(),
        )
        return _OpenAIStream(stream, normalizer)

    def _prepare_tools(self, tools: Any) -> Sequence[dict[str, Any]] | None:
        if tools is None:
            return None
        if isinstance(tools, Sequence) and not isinstance(tools, (str, bytes, bytearray)):
            if not tools:
                return None
            if all(isinstance(tool, Mapping) for tool in tools):
                return [dict(tool) for tool in tools]
            if all(isinstance(tool, ToolSpec) for tool in tools):
                return tool_specs_to_openai(tools)  # type: ignore[arg-type]
        msg = "tools must be a sequence of ToolSpec or mapping objects"
        raise AdapterStreamError(msg)

    def _build_payload(
        self,
        prompt: str,
        *,
        system_prompt: str | None,
        tools: Sequence[dict[str, Any]] | None,
        extra_options: Mapping[str, Any],
    ) -> dict[str, Any]:
        options = dict(self._default_params)
        for key, value in extra_options.items():
            if key in {"messages", "stream", "tools"}:
                msg = f"option '{key}' is reserved by the adapter"
                raise AdapterStreamError(msg)
            options[key] = value

        model_name = options.pop("model", None) or self._default_model
        if not model_name:
            msg = "a model name must be provided"
            raise AdapterStreamError(msg)

        options.setdefault("temperature", 0)

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model_name,
            **options,
            "messages": messages,
            "stream": True,
        }
        if tools is not None:
            payload["tools"] = tools
        return payload


def _default_stream_factory(client: Any, payload: Mapping[str, Any]) -> Any:
    chat = getattr(client, "chat", None)
    if chat is None or not hasattr(chat, "completions"):
        msg = "client must expose chat.completions.create for streaming"
        raise AdapterStreamError(msg)
    completions = chat.completions
    creator = getattr(completions, "create", None)
    if creator is None:
        msg = "client.chat.completions missing 'create'"
        raise AdapterStreamError(msg)
    return creator(**payload)


class _OpenAIStream(AsyncIterator[BaseEvent]):
    """Async iterator that normalizes OpenAI stream chunks."""

    def __init__(self, stream: Any, normalizer: "_OpenAINormalizer") -> None:
        self._stream = stream
        self._iterator = self._coerce_async_iterator(stream)
        self._normalizer = normalizer
        self._buffer: Deque[BaseEvent] = deque()
        self._closed = False
        self._finalized = False
        self._close_lock = asyncio.Lock()

    def __aiter__(self) -> "_OpenAIStream":
        return self

    async def __anext__(self) -> BaseEvent:
        if self._closed and not self._buffer:
            raise StopAsyncIteration

        buffered = self._pop_buffered_event()
        if buffered is not None:
            return await self._finalize_if_needed(buffered)

        while True:
            if self._closed:
                raise StopAsyncIteration

            if self._finalized and not self._buffer:
                await self.aclose()
                raise StopAsyncIteration

            chunk = await self._consume_chunk()
            events = await self._normalizer.normalize_chunk(chunk)
            if not events:
                continue

            self._buffer.extend(events)
            buffered = self._pop_buffered_event()
            if buffered is not None:
                return await self._finalize_if_needed(buffered)

    async def aclose(self) -> None:
        async with self._close_lock:
            if self._closed:
                return
            self._closed = True
            self._buffer.clear()
            await self._close_stream()

    async def _consume_chunk(self) -> dict[str, Any]:
        try:
            raw_chunk = await self._iterator.__anext__()
        except StopAsyncIteration:
            await self.aclose()
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            await self.aclose()
            msg = "OpenAI stream raised an unexpected error"
            raise AdapterStreamError(msg) from exc
        return self._coerce_mapping(raw_chunk)

    async def _finalize_if_needed(self, event: BaseEvent) -> BaseEvent:
        if isinstance(event, FinalEvent):
            self._finalized = True
            if not self._buffer:
                await self.aclose()
        return event

    def _pop_buffered_event(self) -> BaseEvent | None:
        if not self._buffer:
            return None
        return self._buffer.popleft()

    async def _close_stream(self) -> None:
        stream = self._stream
        for closer_name in ("aclose", "close"):
            closer = getattr(stream, closer_name, None)
            if closer is None:
                continue
            result = closer()
            if inspect.isawaitable(result):
                await result
            return

    def _coerce_async_iterator(self, stream: Any) -> AsyncIteratorABC[Any]:
        iterator_factory = getattr(stream, "__aiter__", None)
        if iterator_factory is None or not callable(iterator_factory):
            msg = "stream must support async iteration"
            raise AdapterStreamError(msg)
        try:
            iterator = iterator_factory()
        except TypeError as exc:
            msg = "stream '__aiter__' must be callable without arguments"
            raise AdapterStreamError(msg) from exc

        anext = getattr(iterator, "__anext__", None)
        if anext is None or not callable(anext):
            msg = "stream iterator must define '__anext__'"
            raise AdapterStreamError(msg)
        return iterator

    def _coerce_mapping(self, chunk: Any) -> dict[str, Any]:
        if isinstance(chunk, Mapping):
            return dict(chunk)
        if hasattr(chunk, "model_dump"):
            payload = chunk.model_dump()
            if isinstance(payload, Mapping):
                return dict(payload)
        if hasattr(chunk, "dict"):
            payload = chunk.dict()
            if isinstance(payload, Mapping):
                return dict(payload)
        if hasattr(chunk, "__dict__"):
            return dict(vars(chunk))
        msg = "stream chunk must be a mapping"
        raise AdapterStreamError(msg)


@dataclass
class _ToolCallState:
    call_id: str | None = None
    name: str | None = None
    fragments: list[str] = field(default_factory=list)

    def update_from_payload(self, payload: Mapping[str, Any], *, index: int) -> None:
        call_id = payload.get("id")
        if call_id is not None:
            if not isinstance(call_id, str) or not call_id:
                msg = f"tool call at index {index} is missing a valid id"
                raise AdapterStreamError(msg)
            self.call_id = call_id

        call_type = payload.get("type")
        if call_type is not None and call_type != "function":
            msg = f"tool call at index {index} must have type 'function'"
            raise AdapterStreamError(msg)

        function_payload = payload.get("function")
        if function_payload is not None and not isinstance(function_payload, Mapping):
            msg = f"tool call at index {index} must include a mapping 'function' payload"
            raise AdapterStreamError(msg)

        if isinstance(function_payload, Mapping):
            name_value = function_payload.get("name")
            if name_value is not None:
                if not isinstance(name_value, str) or not name_value:
                    msg = f"tool call at index {index} is missing a valid function name"
                    raise AdapterStreamError(msg)
                self.name = name_value

    def append_fragment(self, fragment: str) -> None:
        self.fragments.append(fragment)

    def require_id(self, *, index: int) -> str:
        if self.call_id is None:
            msg = f"tool call at index {index} is missing an id before emitting arguments"
            raise AdapterStreamError(msg)
        return self.call_id

    def require_name(self, *, index: int) -> str:
        if self.name is None:
            msg = f"tool call at index {index} is missing a function name before emitting arguments"
            raise AdapterStreamError(msg)
        return self.name

    def build_arguments(self, *, index: int) -> dict[str, Any]:
        raw = "".join(self.fragments)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            msg = f"tool call at index {index} returned invalid JSON arguments"
            raise AdapterStreamError(msg) from exc
        if not isinstance(parsed, dict):
            msg = f"tool call at index {index} arguments must decode to an object"
            raise AdapterStreamError(msg)
        return parsed


class _OpenAINormalizer:
    """Normalize raw OpenAI chunks into canonical events."""

    def __init__(
        self,
        *,
        seq_factory: Callable[[], int],
        ts_factory: Callable[[], datetime],
    ) -> None:
        self._next_seq = seq_factory
        self._next_ts = ts_factory
        self._token_index = 0
        self._text_fragments: list[str] = []
        self._tool_states: dict[int, _ToolCallState] = {}
        self._final_emitted = False
        self._last_total_tokens: int | None = None
        self._last_tool_result_output: str | None = None

    async def normalize_chunk(self, chunk: Mapping[str, Any]) -> list[BaseEvent]:
        mapping = self._ensure_mapping(chunk, path="chunk")
        events: list[BaseEvent] = []

        tool_result_payload = mapping.get("tool_result")
        if tool_result_payload is not None:
            events.append(self._normalize_tool_result(tool_result_payload))

        choice = self._extract_choice(mapping)
        if choice is None:
            return events

        finish_reason = self._extract_finish_reason(choice)
        delta = self._extract_delta(choice)

        events.extend(self._normalize_delta(delta, finish_reason))

        if finish_reason == "tool_calls":
            self._text_fragments.clear()

        final_event = self._maybe_build_final_event(mapping, finish_reason)
        if final_event is not None:
            events.append(final_event)
        return events

    def _normalize_delta(self, delta: Mapping[str, Any], finish_reason: str | None) -> list[BaseEvent]:
        events: list[BaseEvent] = []

        content_fragment = delta.get("content")
        if content_fragment is not None:
            if not isinstance(content_fragment, str):
                msg = "OpenAI delta content fragments must be strings"
                raise AdapterStreamError(msg)
            if content_fragment:
                events.append(
                    TokenEvent(
                        seq_id=self._next_seq(),
                        ts=self._next_ts(),
                        content=content_fragment,
                        index=self._token_index,
                    )
                )
                self._token_index += 1
                self._text_fragments.append(content_fragment)
                self._last_tool_result_output = None

        tool_calls_payload = delta.get("tool_calls")
        if tool_calls_payload is not None:
            events.extend(self._normalize_tool_calls(tool_calls_payload, finish_reason))

        return events

    def _normalize_tool_calls(self, payload: Any, finish_reason: str | None) -> list[BaseEvent]:
        if not isinstance(payload, Sequence):
            msg = "OpenAI delta tool_calls payload must be a sequence"
            raise AdapterStreamError(msg)

        events: list[BaseEvent] = []
        for index, item in enumerate(payload):
            mapping = self._ensure_mapping(item, path=f"choices[0].delta.tool_calls[{index}]")

            raw_index = mapping.get("index")
            if not isinstance(raw_index, int):
                msg = f"tool call delta missing integer index at position {index}"
                raise AdapterStreamError(msg)

            state = self._tool_states.setdefault(raw_index, _ToolCallState())
            state.update_from_payload(mapping, index=raw_index)

            function_payload = mapping.get("function")
            fragment = None
            if isinstance(function_payload, Mapping):
                fragment = function_payload.get("arguments")
            if fragment is not None:
                if not isinstance(fragment, str):
                    msg = f"tool call at index {raw_index} arguments must be strings"
                    raise AdapterStreamError(msg)
                if fragment:
                    state.append_fragment(fragment)

            if finish_reason == "tool_calls":
                call_id = state.require_id(index=raw_index)
                name = state.require_name(index=raw_index)
                args = state.build_arguments(index=raw_index)
                events.append(
                    ToolCallEvent(
                        seq_id=self._next_seq(),
                        ts=self._next_ts(),
                        call_id=call_id,
                        name=name,
                        args=args,
                    )
                )
                self._tool_states.pop(raw_index, None)

        return events

    def _normalize_tool_result(self, payload: Any) -> ToolResultEvent:
        mapping = self._ensure_mapping(payload, path="tool_result")

        call_id = mapping.get("id")
        if not isinstance(call_id, str) or not call_id:
            msg = "tool_result.id must be a non-empty string"
            raise AdapterStreamError(msg)

        output = mapping.get("output")
        if not isinstance(output, str):
            msg = "tool_result.output must be a string"
            raise AdapterStreamError(msg)

        self._last_tool_result_output = output
        return ToolResultEvent(
            seq_id=self._next_seq(),
            ts=self._next_ts(),
            call_id=call_id,
            output=output,
        )

    def _maybe_build_final_event(
        self,
        chunk: Mapping[str, Any],
        finish_reason: str | None,
    ) -> FinalEvent | None:
        if self._final_emitted:
            return None

        total_tokens = self._extract_total_tokens(chunk)
        if total_tokens is not None:
            self._last_total_tokens = total_tokens

        if finish_reason not in {"stop", "length", "content_filter"}:
            return None

        output = self._render_final_output()
        self._final_emitted = True
        usage: dict[str, int] | None = None
        if self._last_total_tokens is not None:
            usage = {"total_tokens": self._last_total_tokens}

        return FinalEvent(
            seq_id=self._next_seq(),
            ts=self._next_ts(),
            output=output,
            finish_reason=finish_reason,
            usage=usage,
        )

    def _render_final_output(self) -> str:
        if self._text_fragments:
            return "".join(self._text_fragments)
        if self._last_tool_result_output is not None:
            return self._last_tool_result_output
        return ""

    def _extract_total_tokens(self, chunk: Mapping[str, Any]) -> int | None:
        usage_payload = chunk.get("usage")
        if usage_payload is None:
            return None
        usage = self._ensure_mapping(usage_payload, path="usage")
        total = usage.get("total_tokens")
        if total is None:
            return None
        if isinstance(total, bool) or not isinstance(total, int):
            msg = "usage.total_tokens must be an integer when provided"
            raise AdapterStreamError(msg)
        if total < 0:
            msg = "usage.total_tokens cannot be negative"
            raise AdapterStreamError(msg)
        return total

    def _extract_choice(self, chunk: Mapping[str, Any]) -> Mapping[str, Any] | None:
        choices = chunk.get("choices")
        if choices is None:
            return None
        if not isinstance(choices, Sequence):
            msg = "OpenAI stream chunk choices must be a sequence"
            raise AdapterStreamError(msg)
        if not choices:
            msg = "OpenAI stream chunk choices cannot be empty"
            raise AdapterStreamError(msg)
        choice = choices[0]
        return self._ensure_mapping(choice, path="choices[0]")

    def _extract_delta(self, choice: Mapping[str, Any]) -> Mapping[str, Any]:
        delta = choice.get("delta")
        if delta is None:
            return {}
        return self._ensure_mapping(delta, path="choices[0].delta")

    def _extract_finish_reason(self, choice: Mapping[str, Any]) -> str | None:
        finish_reason = choice.get("finish_reason")
        if finish_reason is None:
            return None
        if not isinstance(finish_reason, str):
            msg = "finish_reason must be a string when provided"
            raise AdapterStreamError(msg)
        return finish_reason

    def _ensure_mapping(self, value: Any, *, path: str) -> Mapping[str, Any]:
        if isinstance(value, Mapping):
            return value
        if hasattr(value, "model_dump"):
            payload = value.model_dump()
            if isinstance(payload, Mapping):
                return payload
        if hasattr(value, "dict"):
            payload = value.dict()
            if isinstance(payload, Mapping):
                return payload
        if hasattr(value, "__dict__"):
            return vars(value)
        msg = f"{path} must be a mapping"
        raise AdapterStreamError(msg)


# Alias close() to aclose() for compatibility with the standard iterator API.
_OpenAIStream.close = _OpenAIStream.aclose  # type: ignore[attr-defined]
