from __future__ import annotations

import asyncio

from foundry.core.adapters.openai import OpenAIAdapter
from foundry.core.adapters.stream import MockStreamIterator, replay_stream

from tests.fixtures import openai_fake
from tests.harness import BaseEvent, collect


def _build_adapter(chunks: list[dict[str, object]]) -> tuple[OpenAIAdapter, openai_fake.FakeAsyncStream, openai_fake.FakeCompletions]:
    client, stream = openai_fake.build_streaming_client(chunks)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")
    return adapter, stream, client.completions


def test_stream_emits_token_events_and_final_event() -> None:
    adapter, stream, completions = _build_adapter(openai_fake.token_only_chunks())

    events = collect(
        adapter,
        prompt="Say hi",
        system_prompt="Greeter",
    )

    assert events == [
        BaseEvent.token(content="Hello", index=0),
        BaseEvent.token(content=", world", index=1),
        BaseEvent.final(output="Hello, world", total_tokens=4),
    ]

    [call] = completions.calls
    assert call["stream"] is True
    assert stream.closed


def test_stream_tool_call_flow_matches_mock_iterator() -> None:
    adapter, stream, completions = _build_adapter(openai_fake.tool_call_chunks())

    events = collect(
        adapter,
        prompt="Add 1 and 3",
        system_prompt="Calculator",
    )

    expected_events = asyncio.run(replay_stream(MockStreamIterator("tool_call")))
    expected = [BaseEvent.from_stream_event(event) for event in expected_events]

    assert events == expected

    [call] = completions.calls
    assert call["stream"] is True
    assert stream.closed
