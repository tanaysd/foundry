"""Deterministic OpenAI streaming fixtures for offline adapter tests."""

from __future__ import annotations

import asyncio
from collections import deque
from types import SimpleNamespace
from typing import Any, Deque, Iterable, Mapping, Sequence

StreamChunk = Mapping[str, Any]


class FakeAsyncStream:
    """Async iterator that replays pre-defined OpenAI chunks."""

    def __init__(self, chunks: Iterable[StreamChunk]) -> None:
        self._chunks: Deque[dict[str, Any]] = deque(dict(chunk) for chunk in chunks)
        self.closed = False

    def __aiter__(self) -> "FakeAsyncStream":
        return self

    async def __anext__(self) -> dict[str, Any]:
        if not self._chunks:
            raise StopAsyncIteration
        await asyncio.sleep(0)
        return self._chunks.popleft()

    async def aclose(self) -> None:
        self.closed = True


class FakeCompletions:
    """Minimal stub for ``client.chat.completions``."""

    def __init__(self, stream: FakeAsyncStream) -> None:
        self._stream = stream
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeAsyncStream:
        self.calls.append(dict(kwargs))
        return self._stream


def build_streaming_client(chunks: Sequence[StreamChunk]) -> tuple[SimpleNamespace, FakeAsyncStream]:
    """Return a fake OpenAI client and associated stream for the given chunks."""

    stream = FakeAsyncStream(chunks)
    completions = FakeCompletions(stream)
    chat = SimpleNamespace(completions=completions)
    client = SimpleNamespace(chat=chat, completions=completions)
    return client, stream


def token_only_chunks() -> list[dict[str, Any]]:
    """OpenAI chunks representing a token-only streaming response."""

    return [
        {"choices": [{"index": 0, "delta": {"content": "Hello"}}]},
        {"choices": [{"index": 0, "delta": {"content": ", world"}}]},
        {
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 4},
        },
    ]


def tool_call_chunks() -> list[dict[str, Any]]:
    """OpenAI chunks representing a streaming tool call flow."""

    return [
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


def create_openai_stream(client: Any, payload: Mapping[str, Any]) -> FakeAsyncStream:
    """Replica of the adapter's streaming factory that records invocations."""

    return client.completions.create(**payload)


__all__ = [
    "FakeAsyncStream",
    "FakeCompletions",
    "build_streaming_client",
    "create_openai_stream",
    "token_only_chunks",
    "tool_call_chunks",
]
