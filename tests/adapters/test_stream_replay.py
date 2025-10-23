from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from foundry.core.adapters.stream import (
    FinalEvent,
    MockStreamIterator,
    TokenEvent,
    replay_events,
)


def test_replay_events_collapses_mock_stream_output() -> None:
    iterator = MockStreamIterator("simple")

    result = asyncio.run(replay_events(iterator))

    assert result == "Hello, world"
    assert getattr(iterator, "_closed")


def test_replay_events_handles_token_only_stream() -> None:
    async def _token_stream() -> AsyncIterator[TokenEvent | FinalEvent]:
        yield TokenEvent(content="Alpha", index=0)
        yield TokenEvent(content="Beta", index=1)

    result = asyncio.run(replay_events(_token_stream()))

    assert result == "AlphaBeta"


def test_replay_events_appends_mismatched_final_output() -> None:
    async def _mismatched_stream() -> AsyncIterator[TokenEvent | FinalEvent]:
        yield TokenEvent(content="Partial", index=0)
        yield FinalEvent(output="Complete")

    result = asyncio.run(replay_events(_mismatched_stream()))

    assert result == "PartialComplete"
