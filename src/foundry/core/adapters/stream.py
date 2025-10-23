"""Canonical streaming event schema and base iterator primitives."""

from __future__ import annotations

import abc
import asyncio
import inspect
from collections import deque
from dataclasses import dataclass
from typing import Any, AsyncIterator, Deque, Dict, List, Optional, Protocol, Union


@dataclass(slots=True)
class TokenEvent:
    """Incremental assistant token emitted during streaming generation."""

    content: str
    index: int


@dataclass(slots=True)
class ToolCallEvent:
    """Partial tool invocation emitted while arguments are streamed."""

    id: str
    name: str
    args_fragment: str
    is_final: bool = False


@dataclass(slots=True)
class ToolResultEvent:
    """Result payload returned from a previously announced tool call."""

    id: str
    output: str


@dataclass(slots=True)
class FinalEvent:
    """Terminal event containing the consolidated assistant output."""

    output: str
    total_tokens: Optional[int] = None


StreamEvent = Union[TokenEvent, ToolCallEvent, ToolResultEvent, FinalEvent]


class BaseStreamIterator(AsyncIterator[StreamEvent], metaclass=abc.ABCMeta):
    """Shared async iterator driving provider-specific streaming adapters.

    Subclasses are responsible for sourcing raw provider chunks by
    implementing :meth:`_get_next_chunk`. Each chunk is normalized into one or
    more :class:`StreamEvent` instances via a :class:`StreamNormalizer`. The
    iterator buffers normalized events so consumers receive a linear stream of
    canonical event objects regardless of how providers batch their updates.
    """

    def __init__(self, normalizer: StreamNormalizer) -> None:
        self._normalizer = normalizer
        self._buffer: Deque[StreamEvent] = deque()
        self._closed = False
        self._finalized = False
        self._close_lock = asyncio.Lock()

    def __aiter__(self) -> BaseStreamIterator:
        return self

    async def __anext__(self) -> StreamEvent:
        if self._closed and not self._buffer:
            raise StopAsyncIteration

        if self._finalized and not self._buffer:
            await self.close()
            raise StopAsyncIteration

        buffered = self._pop_buffered_event()
        if buffered is not None:
            return await self._finalize_if_needed(buffered)

        while True:
            if self._closed:
                raise StopAsyncIteration

            if self._finalized:
                await self.close()
                raise StopAsyncIteration

            chunk = await self._consume_chunk()
            events = await self._normalizer.normalize_chunk(chunk)
            if not events:
                continue

            self._buffer.extend(events)
            buffered = self._pop_buffered_event()
            if buffered is not None:
                return await self._finalize_if_needed(buffered)

    async def close(self) -> None:
        """Release provider resources and prevent additional iteration."""

        async with self._close_lock:
            if self._closed:
                return

            self._closed = True
            self._buffer.clear()
            await self._on_close()

    async def _consume_chunk(self) -> Dict[str, Any]:
        try:
            return await self._get_next_chunk()
        except StopAsyncIteration:
            await self.close()
            raise

    async def _finalize_if_needed(self, event: StreamEvent) -> StreamEvent:
        if isinstance(event, FinalEvent):
            self._finalized = True
            if not self._buffer:
                await self.close()
        return event

    def _pop_buffered_event(self) -> StreamEvent | None:
        if not self._buffer:
            return None
        return self._buffer.popleft()

    @abc.abstractmethod
    async def _get_next_chunk(self) -> Dict[str, Any]:
        """Retrieve the next raw chunk from the provider stream."""

    async def _on_close(self) -> None:
        """Allow subclasses to dispose provider resources when closing."""


class StreamNormalizer(Protocol):
    async def normalize_chunk(self, chunk: Dict[str, Any]) -> List[StreamEvent]:
        """Map a provider-specific chunk into canonical stream events."""


class _MockStreamNormalizer(StreamNormalizer):
    async def normalize_chunk(self, chunk: Dict[str, Any]) -> List[StreamEvent]:
        events = chunk.get("events", [])
        return list(events)


class MockStreamIterator(BaseStreamIterator):
    """Deterministic in-memory stream iterator for testing pipelines."""

    def __init__(self, scenario: str = "simple") -> None:
        self._scenario = scenario
        self._events: Deque[StreamEvent] = deque(self._make_events(scenario))
        super().__init__(_MockStreamNormalizer())

    async def _get_next_chunk(self) -> Dict[str, Any]:
        await asyncio.sleep(0)
        if not self._events:
            raise StopAsyncIteration
        event = self._events.popleft()
        return {"events": [event]}

    async def close(self) -> None:
        await super().close()

    @classmethod
    def _make_events(cls, scenario: str) -> List[StreamEvent]:
        if scenario == "simple":
            return [
                TokenEvent(content="Hello", index=0),
                TokenEvent(content=", world", index=1),
                FinalEvent(output="Hello, world", total_tokens=4),
            ]
        if scenario == "tool_call":
            return [
                TokenEvent(content="Calling calculator", index=0),
                ToolCallEvent(
                    id="tool-1",
                    name="sum",
                    args_fragment="{\"a\": 1",
                    is_final=False,
                ),
                ToolCallEvent(
                    id="tool-1",
                    name="sum",
                    args_fragment=", \"b\": 3}",
                    is_final=True,
                ),
                ToolResultEvent(id="tool-1", output="Sum is 4"),
                FinalEvent(output="Sum is 4", total_tokens=6),
            ]
        raise ValueError(f"Unknown mock streaming scenario: {scenario!r}")


async def replay_stream(iterator: BaseStreamIterator) -> List[StreamEvent]:
    """Collect all events emitted by a stream iterator."""

    events: List[StreamEvent] = []
    try:
        async for event in iterator:
            events.append(event)
    finally:
        await iterator.close()
    return events


async def replay_events(events: AsyncIterator[StreamEvent]) -> str:
    """Concatenate TokenEvent fragments and FinalEvent output into a single string."""

    fragments: List[str] = []
    final_output: Optional[str] = None
    closers = []

    for closer_name in ("close", "aclose"):
        closer = getattr(events, closer_name, None)
        if closer is not None and callable(closer):
            closers.append(closer)

    try:
        async for event in events:
            if isinstance(event, TokenEvent):
                fragments.append(event.content)
            elif isinstance(event, FinalEvent):
                final_output = event.output
    finally:
        for closer in closers:
            result = closer()
            if inspect.isawaitable(result):
                await result

    token_output = "".join(fragments)
    if final_output is None:
        return token_output
    if token_output and token_output != final_output:
        return token_output + final_output
    return final_output

