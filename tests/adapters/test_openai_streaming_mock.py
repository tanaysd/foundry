from __future__ import annotations

import asyncio

from foundry.core.adapters.stream import (
    FinalEvent,
    MockStreamIterator,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    replay_stream,
)


def test_simple_scenario_emits_expected_events() -> None:
    iterator = MockStreamIterator("simple")

    events = asyncio.run(replay_stream(iterator))

    assert events == [
        TokenEvent(content="Hello", index=0),
        TokenEvent(content=", world", index=1),
        FinalEvent(output="Hello, world", total_tokens=4),
    ]
    assert [type(event) for event in events] == [TokenEvent, TokenEvent, FinalEvent]


def test_tool_call_scenario_is_deterministic() -> None:
    first_run = asyncio.run(replay_stream(MockStreamIterator("tool_call")))
    second_run = asyncio.run(replay_stream(MockStreamIterator("tool_call")))

    assert first_run == [
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
    assert [type(event) for event in first_run] == [
        TokenEvent,
        ToolCallEvent,
        ToolCallEvent,
        ToolResultEvent,
        FinalEvent,
    ]
    assert first_run == second_run
