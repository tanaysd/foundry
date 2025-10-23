from __future__ import annotations

import asyncio
from dataclasses import is_dataclass
from typing import Any, Dict, Iterable, List

import pytest

from foundry.core.adapters.stream import (
    BaseStreamIterator,
    FinalEvent,
    StreamEvent,
    StreamNormalizer,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)


def test_event_dataclasses_are_slot_based() -> None:
    assert is_dataclass(TokenEvent)
    assert is_dataclass(ToolCallEvent)
    assert is_dataclass(ToolResultEvent)
    assert is_dataclass(FinalEvent)

    for cls, expected_slots in (
        (TokenEvent, {"content", "index"}),
        (ToolCallEvent, {"id", "name", "args_fragment", "is_final"}),
        (ToolResultEvent, {"id", "output"}),
        (FinalEvent, {"output", "total_tokens"}),
    ):
        assert set(getattr(cls, "__slots__")) == expected_slots


class DummyNormalizer(StreamNormalizer):
    def __init__(self, responses: Iterable[List[StreamEvent]]) -> None:
        self._responses = iter(responses)
        self.seen_chunks: List[Dict[str, Any]] = []

    async def normalize_chunk(self, chunk: Dict[str, Any]) -> List[StreamEvent]:
        self.seen_chunks.append(chunk)
        try:
            return next(self._responses)
        except StopIteration:
            return []


class DummyStream(BaseStreamIterator):
    def __init__(self, *, chunks: Iterable[Dict[str, Any]], normalizer: StreamNormalizer) -> None:
        super().__init__(normalizer)
        self._chunks = iter(chunks)
        self.closed = False
        self.close_count = 0

    async def _get_next_chunk(self) -> Dict[str, Any]:
        try:
            return next(self._chunks)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def _on_close(self) -> None:
        self.close_count += 1
        self.closed = True


def test_iterator_streams_normalized_events() -> None:
    chunks = [{"id": 1}, {"id": 2}, {"id": 3}]
    normalizer = DummyNormalizer(
        responses=[
            [TokenEvent(content="Hel", index=0), TokenEvent(content="lo", index=1)],
            [
                ToolCallEvent(
                    id="call-1",
                    name="do",
                    args_fragment="{\"x\":",
                    is_final=False,
                ),
                ToolCallEvent(
                    id="call-1",
                    name="do",
                    args_fragment="1}",
                    is_final=True,
                ),
            ],
            [
                ToolResultEvent(id="call-1", output="ok"),
                FinalEvent(output="Hello", total_tokens=4),
            ],
        ]
    )

    stream = DummyStream(chunks=chunks, normalizer=normalizer)

    async def _gather() -> List[StreamEvent]:
        return [event async for event in stream]

    events = asyncio.run(_gather())

    assert events == [
        TokenEvent(content="Hel", index=0),
        TokenEvent(content="lo", index=1),
        ToolCallEvent(id="call-1", name="do", args_fragment='{"x":', is_final=False),
        ToolCallEvent(id="call-1", name="do", args_fragment="1}", is_final=True),
        ToolResultEvent(id="call-1", output="ok"),
        FinalEvent(output="Hello", total_tokens=4),
    ]
    assert stream.close_count == 1
    assert stream.closed
    assert normalizer.seen_chunks == chunks


def test_iterator_skips_empty_batches_and_stops_after_final_event() -> None:
    chunks = [{"id": "empty"}, {"id": "payload"}, {"id": "ignored"}]
    normalizer = DummyNormalizer(
        responses=[
            [],
            [TokenEvent(content="A", index=0), FinalEvent(output="done")],
            [TokenEvent(content="extra", index=1)],
        ]
    )

    stream = DummyStream(chunks=chunks, normalizer=normalizer)

    async def _gather() -> List[StreamEvent]:
        return [event async for event in stream]

    events = asyncio.run(_gather())

    assert events == [TokenEvent(content="A", index=0), FinalEvent(output="done")]
    # The iterator closes as soon as the final event is emitted.
    assert stream.close_count == 1
    assert normalizer.seen_chunks == chunks[:2]


def test_close_is_idempotent_and_prevents_additional_reads() -> None:
    normalizer = DummyNormalizer(responses=[[TokenEvent(content="x", index=0)]])
    stream = DummyStream(chunks=[{"id": 1}], normalizer=normalizer)

    asyncio.run(stream.close())
    asyncio.run(stream.close())

    assert stream.close_count == 1
    assert stream.closed

    async def _anext() -> StreamEvent:
        return await anext(stream)

    with pytest.raises(StopAsyncIteration):
        asyncio.run(_anext())
