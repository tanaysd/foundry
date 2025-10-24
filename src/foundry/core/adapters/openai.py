"""OpenAI provider adapter with deterministic streaming integration."""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..errors import AdapterError
from ..message import Message, MessageRole
from .base import ModelAdapter
from .stream import (
    BaseStreamIterator,
    FinalEvent,
    StreamNormalizer,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from .toolbridge import ToolSpec, tool_specs_to_openai
from .utils import messages_to_openai, openai_to_messages


def create_openai_stream(client: Any, payload: Mapping[str, Any]) -> Any:
    """Create a streaming iterator using the provided OpenAI client."""

    return client.chat.completions.create(**payload)


class OpenAIAdapter(ModelAdapter):
    """Translate Foundry messages to OpenAI's chat completion API."""

    def __init__(
        self,
        client: Any,
        *,
        default_model: str | None = None,
        default_params: Mapping[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._default_model = default_model
        self._default_params = dict(default_params or {})

        if "model" in self._default_params and self._default_model is None:
            model_value = self._default_params.pop("model")
            self._default_model = str(model_value)

        reserved = {"messages", "stream"}
        conflict = reserved.intersection(self._default_params)
        if conflict:
            joined = ", ".join(sorted(conflict))
            msg = f"default parameters cannot include reserved keys: {joined}"
            raise ValueError(msg)

    def generate(
        self,
        messages: Sequence[Message],
        /,
        *,
        tools: Any | None = None,
        stream: bool = False,
        **options: Any,
    ) -> Message:
        if stream:
            msg = "streaming is not supported"
            raise AdapterError(msg)
        if not messages:
            msg = "at least one message is required"
            raise AdapterError(msg)

        model_name = self._resolve_model(options)

        prepared_tools = self._prepare_tools(tools)

        request_payload = self._build_payload(
            messages,
            model_name,
            options,
            tools=prepared_tools,
        )

        try:
            response = self._client.chat.completions.create(**request_payload)
        except Exception as exc:  # pragma: no cover - transport errors
            msg = "OpenAI client call failed"
            raise AdapterError(msg) from exc

        choice = self._extract_first_choice(response)
        message_payload = self._extract_choice_message(choice)

        assistant_messages = openai_to_messages([message_payload])
        assistant = assistant_messages[0]
        if assistant.role is not MessageRole.ASSISTANT:
            msg = "OpenAI returned a non-assistant message"
            raise AdapterError(msg)
        return assistant

    def stream(
        self,
        messages: Sequence[Message],
        /,
        *,
        tools: Any | None = None,
        **options: Any,
    ) -> BaseStreamIterator:
        if not messages:
            msg = "at least one message is required"
            raise AdapterError(msg)

        model_name = self._resolve_model(options)
        prepared_tools = self._prepare_tools(tools)

        request_payload = self._build_payload(
            messages,
            model_name,
            options,
            tools=prepared_tools,
        )
        request_payload["stream"] = True

        try:
            stream = create_openai_stream(self._client, request_payload)
        except Exception as exc:  # pragma: no cover - transport errors
            msg = "OpenAI client call failed"
            raise AdapterError(msg) from exc

        return OpenAIStreamIterator(stream)

    def _resolve_model(self, options: dict[str, Any]) -> str:
        model_option = options.pop("model", None)
        model_name = model_option or self._default_model
        if not model_name:
            msg = "a model name must be provided"
            raise AdapterError(msg)
        return str(model_name)

    def _build_payload(
        self,
        messages: Sequence[Message],
        model_name: str,
        options: Mapping[str, Any],
        *,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        request_payload: dict[str, Any] = {"model": model_name, **self._default_params}
        for key, value in options.items():
            if key in {"messages", "stream", "tools"}:
                msg = f"option '{key}' is managed by the adapter"
                raise AdapterError(msg)
            request_payload[key] = value

        request_payload.setdefault("temperature", 0)
        request_payload["messages"] = messages_to_openai(messages)
        if tools:
            request_payload["tools"] = tools
        return request_payload

    def _prepare_tools(self, tools: Sequence[ToolSpec] | None) -> list[dict[str, Any]] | None:
        if tools in (None, [], ()):  # treat empty as absent
            return None

        if isinstance(tools, Mapping):
            msg = "tools must be a sequence of ToolSpec instances"
            raise AdapterError(msg)

        if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes, bytearray)):
            msg = "tools must be a sequence of ToolSpec instances"
            raise AdapterError(msg)

        return tool_specs_to_openai(tools)

    def _extract_first_choice(self, response: Any) -> Any:
        choices = None
        if isinstance(response, Mapping):
            choices = response.get("choices")
        else:
            choices = getattr(response, "choices", None)

        if not isinstance(choices, Sequence) or not choices:
            msg = "OpenAI response missing choices"
            raise AdapterError(msg)
        return choices[0]

    def _extract_choice_message(self, choice: Any) -> Mapping[str, Any]:
        message_payload: Any
        if isinstance(choice, Mapping):
            message_payload = choice.get("message")
        else:
            message_payload = getattr(choice, "message", None)

        if message_payload is None:
            msg = "OpenAI choice missing message payload"
            raise AdapterError(msg)

        if isinstance(message_payload, Message):
            return {"role": message_payload.role.value, "content": message_payload.content}

        if hasattr(message_payload, "model_dump"):
            dump = getattr(message_payload, "model_dump")
            dumped = dump()
            if not isinstance(dumped, Mapping):
                msg = "model_dump() must return a mapping"
                raise AdapterError(msg)
            return dumped

        if isinstance(message_payload, Mapping):
            return message_payload

        msg = "unsupported OpenAI message payload type"
        raise AdapterError(msg)


class OpenAIStreamIterator(BaseStreamIterator):
    """Stream iterator that converts OpenAI chunks into canonical events."""

    def __init__(
        self,
        stream: Any,
        *,
        normalizer: StreamNormalizer | None = None,
    ) -> None:
        self._stream = stream
        self._iterator = self._coerce_async_iterator(stream)
        self._stream_closed = False
        super().__init__(normalizer or OpenAIStreamNormalizer())

    async def _get_next_chunk(self) -> dict[str, Any]:
        try:
            raw_chunk = await self._iterator.__anext__()
        except StopAsyncIteration:
            raise
        except Exception as exc:  # pragma: no cover - defensive transport wrapper
            msg = "OpenAI stream raised an unexpected error"
            raise AdapterError(msg) from exc

        return self._coerce_mapping(raw_chunk)

    async def _on_close(self) -> None:
        if self._stream_closed:
            return
        self._stream_closed = True

        for closer_name in ("aclose", "close"):
            closer = getattr(self._stream, closer_name, None)
            if closer is None:
                continue
            result = closer()
            if inspect.isawaitable(result):
                await result
            return

    def _coerce_async_iterator(self, stream: Any) -> Any:
        iterator_factory = getattr(stream, "__aiter__", None)
        if iterator_factory is None or not callable(iterator_factory):
            msg = "OpenAI stream must support async iteration"
            raise AdapterError(msg)
        try:
            iterator = iterator_factory()
        except TypeError as exc:
            msg = "OpenAI stream '__aiter__' must be callable without arguments"
            raise AdapterError(msg) from exc

        if not hasattr(iterator, "__anext__"):
            msg = "OpenAI stream iterator must define '__anext__'"
            raise AdapterError(msg)
        return iterator

    def _coerce_mapping(self, chunk: Any) -> dict[str, Any]:
        if isinstance(chunk, Mapping):
            return dict(chunk)

        if hasattr(chunk, "model_dump"):
            mapping = chunk.model_dump()
            if isinstance(mapping, Mapping):
                return dict(mapping)

        if hasattr(chunk, "dict"):
            mapping = chunk.dict()
            if isinstance(mapping, Mapping):
                return dict(mapping)

        if hasattr(chunk, "__dict__"):
            return dict(vars(chunk))

        msg = "OpenAI stream chunk must be a mapping"
        raise AdapterError(msg)


@dataclass
class _ToolCallState:
    """Track incremental metadata for a streaming tool call."""

    call_id: str | None = None
    name: str | None = None

    def update_from_payload(self, payload: Mapping[str, Any], *, index: int) -> None:
        call_id = payload.get("id")
        if call_id is not None:
            if not isinstance(call_id, str) or not call_id:
                msg = f"tool call at index {index} is missing a valid id"
                raise AdapterError(msg)
            self.call_id = call_id

        call_type = payload.get("type")
        if call_type is not None and call_type != "function":
            msg = f"tool call at index {index} must have type 'function'"
            raise AdapterError(msg)

        function_payload = payload.get("function")
        if function_payload is not None and not isinstance(function_payload, Mapping):
            msg = f"tool call at index {index} must include a mapping 'function' payload"
            raise AdapterError(msg)

        if isinstance(function_payload, Mapping):
            name_value = function_payload.get("name")
            if name_value is not None:
                if not isinstance(name_value, str) or not name_value:
                    msg = f"tool call at index {index} is missing a valid function name"
                    raise AdapterError(msg)
                self.name = name_value

    def extract_arguments(
        self,
        function_payload: Mapping[str, Any] | None,
        *,
        index: int,
    ) -> str | None:
        if function_payload is None:
            return None
        if not isinstance(function_payload, Mapping):
            msg = f"tool call at index {index} must describe arguments using a mapping"
            raise AdapterError(msg)

        fragment = function_payload.get("arguments")
        if fragment is None:
            return None
        if not isinstance(fragment, str):
            msg = f"tool call at index {index} arguments must be a string fragment"
            raise AdapterError(msg)
        if not fragment:
            return None
        return fragment

    def require_id(self, *, index: int) -> str:
        if self.call_id is None:
            msg = f"tool call at index {index} is missing an id before emitting arguments"
            raise AdapterError(msg)
        return self.call_id

    def require_name(self, *, index: int) -> str:
        if self.name is None:
            msg = f"tool call at index {index} is missing a function name before emitting arguments"
            raise AdapterError(msg)
        return self.name


class OpenAIStreamNormalizer(StreamNormalizer):
    """Normalize OpenAI streaming chunks into canonical events."""

    def __init__(self) -> None:
        self._token_index = 0
        self._text_fragments: list[str] = []
        self._tool_states: dict[int, _ToolCallState] = {}
        self._final_emitted = False
        self._last_total_tokens: int | None = None
        self._last_tool_result_output: str | None = None

    async def normalize_chunk(self, chunk: Mapping[str, Any]) -> list[TokenEvent | ToolCallEvent | ToolResultEvent | FinalEvent]:
        mapping = self._ensure_mapping(chunk, path="chunk")
        events: list[TokenEvent | ToolCallEvent | ToolResultEvent | FinalEvent] = []

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
            self._reset_text_fragments()

        final_event = self._maybe_build_final_event(mapping, finish_reason)
        if final_event is not None:
            events.append(final_event)
        return events

    def _normalize_delta(
        self,
        delta: Mapping[str, Any],
        finish_reason: str | None,
    ) -> list[TokenEvent | ToolCallEvent]:
        events: list[TokenEvent | ToolCallEvent] = []

        content_fragment = delta.get("content")
        if content_fragment is not None:
            if not isinstance(content_fragment, str):
                msg = "OpenAI delta content fragments must be strings"
                raise AdapterError(msg)
            if content_fragment:
                events.append(TokenEvent(content=content_fragment, index=self._token_index))
                self._token_index += 1
                self._text_fragments.append(content_fragment)
                self._last_tool_result_output = None

        tool_calls_payload = delta.get("tool_calls")
        if tool_calls_payload is not None:
            events.extend(self._normalize_tool_calls(tool_calls_payload, finish_reason))

        return events

    def _normalize_tool_calls(
        self,
        payload: Any,
        finish_reason: str | None,
    ) -> list[ToolCallEvent]:
        if not isinstance(payload, Sequence):
            msg = "OpenAI delta tool_calls payload must be a sequence"
            raise AdapterError(msg)

        events: list[ToolCallEvent] = []
        for index, item in enumerate(payload):
            mapping = self._ensure_mapping(item, path=f"choices[0].delta.tool_calls[{index}]")

            raw_index = mapping.get("index")
            if not isinstance(raw_index, int):
                msg = f"tool call delta missing integer index at position {index}"
                raise AdapterError(msg)

            state = self._tool_states.setdefault(raw_index, _ToolCallState())
            state.update_from_payload(mapping, index=raw_index)

            function_payload = mapping.get("function")
            fragment = state.extract_arguments(function_payload, index=raw_index)
            if fragment is None:
                continue

            call_id = state.require_id(index=raw_index)
            name = state.require_name(index=raw_index)
            events.append(
                ToolCallEvent(
                    id=call_id,
                    name=name,
                    args_fragment=fragment,
                    is_final=finish_reason == "tool_calls",
                )
            )

        return events

    def _normalize_tool_result(self, payload: Any) -> ToolResultEvent:
        mapping = self._ensure_mapping(payload, path="tool_result")

        call_id = mapping.get("id")
        if not isinstance(call_id, str) or not call_id:
            msg = "tool_result.id must be a non-empty string"
            raise AdapterError(msg)

        output = mapping.get("output")
        if not isinstance(output, str):
            msg = "tool_result.output must be a string"
            raise AdapterError(msg)

        self._last_tool_result_output = output
        return ToolResultEvent(id=call_id, output=output)

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
        return FinalEvent(output=output, total_tokens=self._last_total_tokens)

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
            raise AdapterError(msg)
        if total < 0:
            msg = "usage.total_tokens cannot be negative"
            raise AdapterError(msg)
        return total

    def _extract_choice(self, chunk: Mapping[str, Any]) -> Mapping[str, Any] | None:
        choices = chunk.get("choices")
        if choices is None:
            return None
        if not isinstance(choices, Sequence):
            msg = "OpenAI stream chunk choices must be a sequence"
            raise AdapterError(msg)
        if not choices:
            return None
        return self._ensure_mapping(choices[0], path="choices[0]")

    def _extract_finish_reason(self, choice: Mapping[str, Any]) -> str | None:
        finish_reason = choice.get("finish_reason")
        if finish_reason is None:
            return None
        if not isinstance(finish_reason, str):
            msg = "OpenAI finish_reason must be a string when present"
            raise AdapterError(msg)
        return finish_reason

    def _extract_delta(self, choice: Mapping[str, Any]) -> Mapping[str, Any]:
        delta = choice.get("delta")
        if delta is None:
            return {}
        return self._ensure_mapping(delta, path="choices[0].delta")

    def _reset_text_fragments(self) -> None:
        self._text_fragments = []

    def _ensure_mapping(self, value: Any, *, path: str) -> Mapping[str, Any]:
        if isinstance(value, Mapping):
            return value

        if hasattr(value, "model_dump"):
            mapping = value.model_dump()
            if isinstance(mapping, Mapping):
                return mapping

        if hasattr(value, "dict"):
            mapping = value.dict()
            if isinstance(mapping, Mapping):
                return mapping

        if hasattr(value, "__dict__"):
            return vars(value)

        msg = f"{path} must be a mapping"
        raise AdapterError(msg)
