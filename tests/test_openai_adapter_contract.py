from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

from foundry.adapters import AdapterStreamError, BaseAdapter, FinalEvent, OpenAIAdapter, TokenEvent
from tests.fixtures import openai_fake


async def _collect(iterator: AsyncIterator[TokenEvent | FinalEvent]) -> list[TokenEvent | FinalEvent]:
    return [event async for event in iterator]


def test_openai_adapter_implements_base_adapter_protocol() -> None:
    client, _ = openai_fake.build_streaming_client(openai_fake.token_only_chunks())
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    assert isinstance(adapter, BaseAdapter)

    stream = adapter.stream("Ping")
    events = asyncio.run(_collect(stream))

    assert len(events) == 3
    assert isinstance(events[0], TokenEvent)
    assert isinstance(events[-1], FinalEvent)


def test_stream_returns_async_iterator() -> None:
    client, _ = openai_fake.build_streaming_client(openai_fake.token_only_chunks())
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    stream = adapter.stream("Ping")

    assert hasattr(stream, "__aiter__")
    assert hasattr(stream, "__anext__")

    first_event = asyncio.run(stream.__anext__())
    assert isinstance(first_event, TokenEvent)

    asyncio.run(stream.aclose())


@pytest.mark.parametrize("invalid_prompt", [None, "", 123])
def test_invalid_prompt_raises_error(invalid_prompt: object) -> None:
    client, _ = openai_fake.build_streaming_client(openai_fake.token_only_chunks())
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    with pytest.raises(AdapterStreamError):
        adapter.stream(invalid_prompt)  # type: ignore[arg-type]
