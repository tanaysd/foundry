from __future__ import annotations

import asyncio
from datetime import datetime

from foundry.adapters import FinalEvent, OpenAIAdapter, TokenEvent, ToolCallEvent, ToolResultEvent
from foundry.adapters.openai_adapter import TS_ORIGIN, TS_STEP
from tests.fixtures import openai_fake


async def _collect_events(adapter: OpenAIAdapter, *, prompt: str) -> list[TokenEvent | ToolCallEvent | ToolResultEvent | FinalEvent]:
    stream = adapter.stream(prompt)
    return [event async for event in stream]


def _expected_timestamp(offset: int) -> datetime:
    return TS_ORIGIN + TS_STEP * offset


def test_token_only_stream_matches_expected_sequence() -> None:
    client, stream = openai_fake.build_streaming_client(openai_fake.token_only_chunks())
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    events = asyncio.run(_collect_events(adapter, prompt="Say hi"))

    assert events == [
        TokenEvent(seq_id=0, ts=_expected_timestamp(0), content="Hello", index=0),
        TokenEvent(seq_id=1, ts=_expected_timestamp(1), content=", world", index=1),
        FinalEvent(
            seq_id=2,
            ts=_expected_timestamp(2),
            output="Hello, world",
            finish_reason="stop",
            usage={"total_tokens": 4},
        ),
    ]

    assert stream.closed


def test_tool_call_flow_emits_canonical_events() -> None:
    client, stream = openai_fake.build_streaming_client(openai_fake.tool_call_chunks())
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    events = asyncio.run(_collect_events(adapter, prompt="Add numbers"))

    assert events == [
        TokenEvent(seq_id=0, ts=_expected_timestamp(0), content="Calling calculator", index=0),
        ToolCallEvent(
            seq_id=1,
            ts=_expected_timestamp(1),
            call_id="tool-1",
            name="sum",
            args={"a": 1, "b": 3},
        ),
        ToolResultEvent(
            seq_id=2,
            ts=_expected_timestamp(2),
            call_id="tool-1",
            output="Sum is 4",
        ),
        FinalEvent(
            seq_id=3,
            ts=_expected_timestamp(3),
            output="Sum is 4",
            finish_reason="stop",
            usage={"total_tokens": 6},
        ),
    ]

    assert stream.closed
