from __future__ import annotations

import asyncio
from asyncio import CancelledError
from collections import deque
from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest

from foundry.core.adapters import ModelAdapter
from foundry.core.adapters.stream import (
    BaseStreamIterator,
    FinalEvent,
    StreamEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from foundry.core.message import Message, MessageRole
from foundry.runtime.loop import AgentRuntime


class _IdentityNormalizer:
    async def normalize_chunk(self, chunk: dict[str, Any]) -> list[StreamEvent]:
        return list(chunk.get("events", []))


class _ListStreamIterator(BaseStreamIterator):
    def __init__(self, events: Sequence[StreamEvent | BaseException]) -> None:
        self._events = deque(events)
        super().__init__(_IdentityNormalizer())

    async def _get_next_chunk(self) -> dict[str, Any]:
        if not self._events:
            raise StopAsyncIteration

        item = self._events.popleft()
        if isinstance(item, BaseException):
            raise item
        return {"events": [item]}


class _MockAdapter(ModelAdapter):
    def __init__(self, events: Sequence[StreamEvent | BaseException]) -> None:
        self._events = list(events)

    def generate(self, messages: Sequence[Message], /, *, tools: Any | None = None, stream: bool = False, **options: Any) -> Message:  # noqa: ARG002
        raise NotImplementedError("streaming-only mock adapter")

    def stream(self, messages: Sequence[Message], /, *, tools: Any | None = None, **options: Any) -> BaseStreamIterator:  # noqa: ARG002
        return _ListStreamIterator(self._events)


def _gather_events(events: AsyncIterator[StreamEvent]) -> list[StreamEvent]:
    async def _collect() -> list[StreamEvent]:
        results: list[StreamEvent] = []
        async for event in events:
            results.append(event)
        return results

    return asyncio.run(_collect())


def _user_message(content: str) -> Message:
    return Message(role=MessageRole.USER, content=content)


def test_agent_runtime_state_machine_updates_metadata_and_state() -> None:
    events: list[StreamEvent] = [
        TokenEvent(content="Calling calculator", index=0),
        ToolCallEvent(id="tool-1", name="sum", args_fragment="{\"a\": 1", is_final=False),
        ToolCallEvent(id="tool-1", name="sum", args_fragment=", \"b\": 3}", is_final=True),
        ToolResultEvent(id="tool-1", output="Sum is 4"),
        FinalEvent(output="Sum is 4", total_tokens=6),
    ]
    adapter = _MockAdapter(events)
    runtime = AgentRuntime(adapter, [_user_message("add two numbers")])

    collected = _gather_events(runtime)

    assert [type(event) for event in collected] == [
        TokenEvent,
        ToolCallEvent,
        ToolCallEvent,
        ToolResultEvent,
        FinalEvent,
    ]

    assert runtime.closed
    assert runtime.state.metadata["token_counts"] == 1

    tool_calls = runtime.state.metadata["tool_calls"]
    assert tool_calls["tool-1"]["args"] == '{"a": 1, "b": 3}'
    assert tool_calls["tool-1"]["is_final"] is True

    tool_results = runtime.state.metadata["tool_results"]
    assert tool_results["tool-1"] == "Sum is 4"

    assert runtime.state.metadata["final_output"] == "Sum is 4"
    assert runtime.state.metadata["total_tokens"] == 6

    # State snapshots are detached from the live state
    snapshot_tokens = runtime.transcript.states[0].tokens
    runtime.state.tokens.clear()
    assert snapshot_tokens, "snapshot should retain token history"


def test_session_transcript_replay_matches_original_events() -> None:
    events: list[StreamEvent] = [
        TokenEvent(content="First", index=0),
        FinalEvent(output="First", total_tokens=1),
    ]
    adapter = _MockAdapter(events)
    runtime = AgentRuntime(adapter, [_user_message("ping")])

    original = _gather_events(runtime)
    replayed = _gather_events(runtime.transcript.replay())

    assert original == replayed
    assert len(runtime.transcript.events) == len(original)


def test_agent_runtime_closes_when_cancelled() -> None:
    events: list[StreamEvent | BaseException] = [
        TokenEvent(content="Starting", index=0),
        CancelledError(),
    ]
    adapter = _MockAdapter(events)
    runtime = AgentRuntime(adapter, [_user_message("hi")])

    async def _consume_with_cancellation() -> None:
        iterator = runtime.__aiter__()
        first = await iterator.__anext__()
        assert isinstance(first, TokenEvent)
        with pytest.raises(CancelledError):
            await iterator.__anext__()

    asyncio.run(_consume_with_cancellation())
    assert runtime.closed
