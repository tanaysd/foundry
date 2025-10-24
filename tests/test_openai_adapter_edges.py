from __future__ import annotations

import asyncio

import pytest

from foundry.adapters import AdapterStreamError, FinalEvent, OpenAIAdapter, TokenEvent
from tests.fixtures import openai_fake


async def _collect_some(iterator, limit: int) -> list:
    events = []
    async for event in iterator:
        events.append(event)
        if len(events) >= limit:
            break
    return events


async def _collect_all(iterator) -> list:
    return [event async for event in iterator]


def test_stream_factory_errors_are_wrapped() -> None:
    def failing_factory(*_args, **_kwargs):
        raise RuntimeError("boom")

    adapter = OpenAIAdapter(object(), default_model="gpt-4o-mini", stream_factory=failing_factory)

    with pytest.raises(AdapterStreamError):
        adapter.stream("Hello")


def test_manual_cancellation_closes_stream() -> None:
    client, stream = openai_fake.build_streaming_client(openai_fake.token_only_chunks())
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    iterator = adapter.stream("Ping")
    events = asyncio.run(_collect_some(iterator, limit=1))

    assert isinstance(events[0], TokenEvent)

    asyncio.run(iterator.aclose())
    assert stream.closed


def test_empty_content_emits_final_event() -> None:
    chunks = [
        {"choices": [{"index": 0, "delta": {}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]

    client, stream = openai_fake.build_streaming_client(chunks)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    events = asyncio.run(_collect_all(adapter.stream("Ping")))

    assert isinstance(events[-1], FinalEvent)
    assert events[-1].output == ""
    assert stream.closed


def test_provider_error_during_iteration_is_wrapped() -> None:
    class FailingStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise RuntimeError("fail")

        async def aclose(self):
            pass

    def factory(_client, _payload):
        return FailingStream()

    adapter = OpenAIAdapter(object(), default_model="gpt-4o-mini", stream_factory=factory)

    iterator = adapter.stream("Hi")

    with pytest.raises(AdapterStreamError):
        asyncio.run(iterator.__anext__())
