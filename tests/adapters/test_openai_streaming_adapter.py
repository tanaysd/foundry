from __future__ import annotations

import asyncio
from collections import deque
from types import SimpleNamespace

from foundry.core import Message, MessageRole
from foundry.core.adapters.openai import OpenAIAdapter
from foundry.core.adapters.stream import (
    FinalEvent,
    MockStreamIterator,
    TokenEvent,
    replay_stream,
)


class FakeAsyncStream:
    def __init__(self, chunks: list[dict[str, object]]) -> None:
        self._chunks: deque[dict[str, object]] = deque(chunks)
        self.closed = False

    def __aiter__(self) -> FakeAsyncStream:
        return self

    async def __anext__(self) -> dict[str, object]:
        if not self._chunks:
            raise StopAsyncIteration
        await asyncio.sleep(0)
        return self._chunks.popleft()

    async def aclose(self) -> None:
        self.closed = True


class FakeCompletions:
    def __init__(self, stream: FakeAsyncStream) -> None:
        self._stream = stream
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> FakeAsyncStream:
        self.calls.append(kwargs)
        return self._stream


def build_streaming_client(chunks: list[dict[str, object]]) -> tuple[SimpleNamespace, FakeAsyncStream]:
    stream = FakeAsyncStream(chunks)
    completions = FakeCompletions(stream)
    chat = SimpleNamespace(completions=completions)
    client = SimpleNamespace(chat=chat, completions=completions)
    return client, stream


def _gather_stream_events(adapter: OpenAIAdapter, messages: list[Message]) -> list[object]:
    iterator = adapter.stream(messages)
    return asyncio.run(replay_stream(iterator))


def test_stream_emits_token_events_and_final_event() -> None:
    chunks = [
        {"choices": [{"index": 0, "delta": {"content": "Hello"}}]},
        {"choices": [{"index": 0, "delta": {"content": ", world"}}]},
        {
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 4},
        },
    ]

    client, stream = build_streaming_client(chunks)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    messages = [
        Message(role=MessageRole.SYSTEM, content="Greeter"),
        Message(role=MessageRole.USER, content="Say hi"),
    ]

    events = _gather_stream_events(adapter, messages)

    assert events == [
        TokenEvent(content="Hello", index=0),
        TokenEvent(content=", world", index=1),
        FinalEvent(output="Hello, world", total_tokens=4),
    ]

    [call] = client.completions.calls
    assert call["stream"] is True
    assert stream.closed


def test_stream_tool_call_flow_matches_mock_iterator() -> None:
    chunks = [
        {"choices": [{"index": 0, "delta": {"content": "Calling calculator"}}]},
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "tool-1",
                                "type": "function",
                                "function": {"name": "sum", "arguments": '{"a": 1'},
                            }
                        ]
                    },
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": ', "b": 3}'},
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
        {"tool_result": {"id": "tool-1", "output": "Sum is 4"}},
        {
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 6},
        },
    ]

    client, stream = build_streaming_client(chunks)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    messages = [
        Message(role=MessageRole.SYSTEM, content="Calculator"),
        Message(role=MessageRole.USER, content="Add 1 and 3"),
    ]

    events = _gather_stream_events(adapter, messages)
    expected = asyncio.run(replay_stream(MockStreamIterator("tool_call")))

    assert events == expected

    [call] = client.completions.calls
    assert call["stream"] is True
    assert stream.closed
