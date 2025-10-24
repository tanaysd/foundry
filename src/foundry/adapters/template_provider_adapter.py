"""Skeleton streaming adapter for building new provider integrations."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from itertools import count
from typing import Any, Deque, Literal

from .base import (
    AdapterStreamError,
    BaseAdapter,
    BaseEvent,
    FinalEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)

__all__ = [
    "TemplateProviderAdapter",
    "TemplateProviderChunk",
    "TS_ORIGIN",
    "TS_STEP",
    "monotonic_seq",
    "stable_ts",
]

TS_ORIGIN = datetime(2024, 1, 1, tzinfo=timezone.utc)
TS_STEP = timedelta(milliseconds=1)


def monotonic_seq(*, start: int = 0) -> Callable[[], int]:
    """Return a callable that yields strictly increasing integers."""

    counter = count(start)

    def _next() -> int:
        return next(counter)

    return _next


def stable_ts(
    *, origin: datetime = TS_ORIGIN, step: timedelta = TS_STEP
) -> Callable[[], datetime]:
    """Return a callable that yields deterministic timestamps."""

    counter = count()

    def _next() -> datetime:
        index = next(counter)
        return origin + step * index

    return _next


EventKind = Literal["token", "tool_call_delta", "tool_result", "final", "keep_alive"]


@dataclass(frozen=True, slots=True)
class TemplateProviderChunk:
    """Example provider chunk used by the template harness.

    Replace this dataclass with the concrete chunk type exposed by the provider.
    Keep the field names aligned with your SDK and adapt the normalizer to match.
    """

    kind: EventKind
    content: str | None = None
    index: int | None = None
    call_id: str | None = None
    name: str | None = None
    args_fragment: str | None = None
    is_final: bool | None = None
    output: str | None = None
    finish_reason: str | None = None
    usage: Mapping[str, int] | None = None


@dataclass(slots=True)
class _BufferedToolCall:
    name: str | None = None
    fragments: list[str] = field(default_factory=list)

    def add_fragment(self, fragment: str | None) -> None:
        if fragment:
            self.fragments.append(fragment)

    def update_name(self, name: str | None) -> None:
        if name:
            self.name = name

    def to_event(self, *, seq: int, ts: datetime, call_id: str) -> ToolCallEvent:
        payload = "".join(self.fragments) or "{}"
        try:
            args = json.loads(payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            msg = f"failed to decode tool call args for {call_id}"
            raise AdapterStreamError(msg) from exc
        if not isinstance(args, Mapping):
            msg = "tool call args must deserialize to a mapping"
            raise AdapterStreamError(msg)
        if self.name is None:
            msg = "tool call name missing when final fragment received"
            raise AdapterStreamError(msg)
        return ToolCallEvent(seq, ts, call_id=call_id, name=self.name, args=dict(args))


class TemplateProviderAdapter(BaseAdapter):
    """Template adapter that normalizes provider streaming chunks.

    Replace the payload builder, stream factory, and normalizer logic with the
    provider-specific behavior while preserving the deterministic sequencing and
    error handling patterns.
    """

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

    def stream(self, prompt: str, /, **kwargs: Any) -> AsyncIterator[BaseEvent]:
        if not isinstance(prompt, str) or not prompt.strip():
            msg = "prompt must be a non-empty string"
            raise AdapterStreamError(msg)

        payload = self._build_payload(prompt, extra_options=kwargs)

        try:
            stream = self._stream_factory(self._client, payload)
        except Exception as exc:  # pragma: no cover - defensive guard
            msg = "provider client call failed"
            raise AdapterStreamError(msg) from exc

        normalizer = _TemplateNormalizer(
            seq_factory=monotonic_seq(),
            ts_factory=stable_ts(),
        )
        return _TemplateProviderStream(stream, normalizer)

    def _build_payload(
        self,
        prompt: str,
        *,
        extra_options: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Build the provider request payload.

        TODO: Translate the Foundry prompt into your provider's payload shape.
        Keep this method deterministic so tests can replay identical requests.
        """

        options = dict(self._default_params)
        options.update(extra_options)

        model_name = options.pop("model", None) or self._default_model
        if not model_name:
            msg = "a model name must be provided"
            raise AdapterStreamError(msg)

        payload = {
            "model": model_name,
            "prompt": prompt,
            **options,
        }
        return payload


def _default_stream_factory(client: Any, payload: Mapping[str, Any]) -> Any:
    """Default factory that expects ``client.stream(prompt=...)`` support."""

    stream = getattr(client, "stream", None)
    if stream is None:
        msg = "client must expose a 'stream' method"
        raise AdapterStreamError(msg)
    result = stream(**payload)
    if result is None:
        msg = "client.stream returned None"
        raise AdapterStreamError(msg)
    return result


class _TemplateProviderStream(AsyncIterator[BaseEvent]):
    """Async iterator that converts provider chunks into canonical events."""

    def __init__(self, stream: Any, normalizer: "_TemplateNormalizer") -> None:
        self._stream = stream
        self._iterator = self._coerce_async_iterator(stream)
        self._normalizer = normalizer
        self._buffer: Deque[BaseEvent] = deque()
        self._closed = False

    def __aiter__(self) -> "_TemplateProviderStream":
        return self

    async def __anext__(self) -> BaseEvent:
        if self._closed and not self._buffer:
            raise StopAsyncIteration

        buffered = self._pop_buffered_event()
        if buffered is not None:
            return await self._finalize_if_needed(buffered)

        chunk = await self._next_chunk()
        events = self._normalizer.consume(chunk)
        self._buffer.extend(events)
        return await self.__anext__()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        aclose = getattr(self._iterator, "aclose", None)
        if aclose is not None:
            await aclose()
        elif hasattr(self._stream, "aclose"):
            await getattr(self._stream, "aclose")()

    async def _finalize_if_needed(self, event: BaseEvent) -> BaseEvent:
        if self._normalizer.finalized and not self._closed:
            await self.aclose()
        return event

    async def _next_chunk(self) -> TemplateProviderChunk:
        try:
            return await self._iterator.__anext__()
        except StopAsyncIteration:  # pragma: no cover - defensive
            self._closed = True
            raise

    def _pop_buffered_event(self) -> BaseEvent | None:
        if not self._buffer:
            return None
        return self._buffer.popleft()

    @staticmethod
    def _coerce_async_iterator(stream: Any) -> AsyncIterator[TemplateProviderChunk]:
        iterator = getattr(stream, "__aiter__", None)
        if iterator is None:
            msg = "stream must be an async iterator"
            raise AdapterStreamError(msg)
        async_iterator = iterator()
        anext = getattr(async_iterator, "__anext__", None)
        if anext is None:
            msg = "stream must implement __anext__"
            raise AdapterStreamError(msg)
        return async_iterator


class _TemplateNormalizer:
    """Normalize provider chunks into canonical Foundry events."""

    def __init__(
        self,
        *,
        seq_factory: Callable[[], int],
        ts_factory: Callable[[], datetime],
    ) -> None:
        self._seq_factory = seq_factory
        self._ts_factory = ts_factory
        self._tool_calls: dict[str, _BufferedToolCall] = {}
        self._final_emitted = False

    @property
    def finalized(self) -> bool:
        return self._final_emitted

    def consume(self, chunk: TemplateProviderChunk) -> list[BaseEvent]:
        if chunk.kind == "keep_alive":
            return []
        if chunk.kind == "token":
            if chunk.content is None or chunk.index is None:
                msg = "token chunk must include content and index"
                raise AdapterStreamError(msg)
            return [
                TokenEvent(
                    seq_id=self._next_seq(),
                    ts=self._next_ts(),
                    content=chunk.content,
                    index=chunk.index,
                )
            ]
        if chunk.kind == "tool_call_delta":
            return self._consume_tool_call_delta(chunk)
        if chunk.kind == "tool_result":
            if chunk.call_id is None or chunk.output is None:
                msg = "tool result chunk missing call_id or output"
                raise AdapterStreamError(msg)
            return [
                ToolResultEvent(
                    seq_id=self._next_seq(),
                    ts=self._next_ts(),
                    call_id=chunk.call_id,
                    output=chunk.output,
                )
            ]
        if chunk.kind == "final":
            if chunk.output is None:
                msg = "final chunk must include output"
                raise AdapterStreamError(msg)
            if self._final_emitted:
                return []
            self._final_emitted = True
            return [
                FinalEvent(
                    seq_id=self._next_seq(),
                    ts=self._next_ts(),
                    output=chunk.output,
                    finish_reason=chunk.finish_reason,
                    usage=dict(chunk.usage or {}),
                )
            ]

        msg = f"unsupported chunk kind: {chunk.kind!r}"
        raise AdapterStreamError(msg)

    def _consume_tool_call_delta(self, chunk: TemplateProviderChunk) -> list[BaseEvent]:
        if chunk.call_id is None:
            msg = "tool call chunk must include call_id"
            raise AdapterStreamError(msg)
        buffer = self._tool_calls.setdefault(chunk.call_id, _BufferedToolCall())
        buffer.update_name(chunk.name)
        buffer.add_fragment(chunk.args_fragment)
        if chunk.is_final:
            event = buffer.to_event(
                seq=self._next_seq(),
                ts=self._next_ts(),
                call_id=chunk.call_id,
            )
            del self._tool_calls[chunk.call_id]
            return [event]
        return []

    def _next_seq(self) -> int:
        return self._seq_factory()

    def _next_ts(self) -> datetime:
        return self._ts_factory()
