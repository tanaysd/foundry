from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import pytest

from foundry.core.adapters import (
    BaseStreamIterator,
    FinalEvent,
    ModelAdapter,
    StreamEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from foundry.core.adapters.stream import MockStreamIterator
from foundry.core.message import Message, MessageRole


class _RecordingStream(MockStreamIterator):
    def __init__(self, scenario: str = "tool_call") -> None:
        super().__init__(scenario)
        self.closed = False

    async def close(self) -> None:
        self.closed = True
        await super().close()


class _MockAdapter(ModelAdapter):
    def __init__(self, scenario: str = "tool_call") -> None:
        self._scenario = scenario

    def generate(
        self,
        messages: Sequence[Message],
        /,
        *,
        tools: Any | None = None,
        stream: bool = False,
        **options: Any,
    ) -> Message:
        raise NotImplementedError("streaming-only stub")

    def stream(
        self,
        messages: Sequence[Message],
        /,
        *,
        tools: Any | None = None,
        **options: Any,
    ) -> BaseStreamIterator:
        if not messages:
            raise ValueError("messages are required for streaming")
        return _RecordingStream(self._scenario)


class _RuntimeStub:
    def __init__(self, adapter: ModelAdapter, messages: Sequence[Message]) -> None:
        self._adapter = adapter
        self._messages = tuple(messages)
        self._iterator: BaseStreamIterator | None = None
        self.closed = False

    def __aiter__(self) -> "_RuntimeStub":
        if self._iterator is None:
            self._iterator = self._adapter.stream(self._messages)
        return self

    async def __anext__(self) -> StreamEvent:
        if self._iterator is None:
            self._iterator = self._adapter.stream(self._messages)
        assert self._iterator is not None

        try:
            event = await self._iterator.__anext__()
        except StopAsyncIteration:
            self.closed = True
            raise

        if isinstance(event, FinalEvent):
            await self._iterator.close()
            self.closed = True
        return event

    async def aclose(self) -> None:
        if self._iterator is None:
            self.closed = True
            return
        if not self.closed:
            await self._iterator.close()
        self.closed = True


def _user_message(content: str) -> Message:
    return Message(role=MessageRole.USER, content=content)


def test_runtime_stub_streams_canonical_events_and_stops_on_final() -> None:
    adapter = _MockAdapter("tool_call")
    runtime = _RuntimeStub(adapter, [_user_message("calculate")])

    async def _consume() -> list[StreamEvent]:
        return [event async for event in runtime]

    events = asyncio.run(_consume())

    assert [type(event) for event in events] == [
        TokenEvent,
        ToolCallEvent,
        ToolCallEvent,
        ToolResultEvent,
        FinalEvent,
    ]

    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert final.output == "Sum is 4"

    assert runtime.closed is True
    iterator = runtime._iterator
    assert iterator is not None
    assert getattr(iterator, "closed", False) is True

    async def _pull_once() -> StreamEvent:
        return await runtime.__anext__()

    with pytest.raises(StopAsyncIteration):
        asyncio.run(_pull_once())
