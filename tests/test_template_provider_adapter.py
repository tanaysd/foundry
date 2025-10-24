from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Iterable

import pytest

from foundry.adapters import (
    AdapterStreamError,
    FinalEvent,
    TemplateProviderAdapter,
    TemplateProviderChunk,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from foundry.adapters.template_provider_adapter import TS_ORIGIN, TS_STEP


class _FakeTemplateStream:
    def __init__(self, chunks: Iterable[TemplateProviderChunk]) -> None:
        self._iterator = iter(chunks)
        self.closed = False

    def __aiter__(self) -> "_FakeTemplateStream":
        return self

    async def __anext__(self) -> TemplateProviderChunk:
        try:
            return next(self._iterator)
        except StopIteration:
            self.closed = True
            raise StopAsyncIteration

    async def aclose(self) -> None:
        self.closed = True


class _FakeTemplateClient:
    def __init__(self, stream: _FakeTemplateStream) -> None:
        self._stream = stream

    def stream(self, *, prompt: str, model: str, **_: object) -> _FakeTemplateStream:
        if not prompt or not model:
            msg = "prompt and model are required"
            raise ValueError(msg)
        return self._stream


async def _collect_events(adapter: TemplateProviderAdapter, *, prompt: str) -> list[
    TokenEvent | ToolCallEvent | ToolResultEvent | FinalEvent
]:
    stream = adapter.stream(prompt)
    return [event async for event in stream]


def _expected_ts(offset: int) -> datetime:
    return TS_ORIGIN + TS_STEP * offset


def test_template_adapter_token_and_tool_call_flow() -> None:
    chunks = [
        TemplateProviderChunk(kind="token", content="Hello", index=0),
        TemplateProviderChunk(
            kind="tool_call_delta",
            call_id="tool-1",
            name="sum",
            args_fragment="{\"a\": 1, \"b\": 3}",
            is_final=True,
        ),
        TemplateProviderChunk(kind="tool_result", call_id="tool-1", output="Sum is 4"),
        TemplateProviderChunk(
            kind="final",
            output="Sum is 4",
            finish_reason="stop",
            usage={"total_tokens": 6},
        ),
    ]
    stream = _FakeTemplateStream(chunks)
    client = _FakeTemplateClient(stream)
    adapter = TemplateProviderAdapter(client, default_model="template-large")

    events = asyncio.run(_collect_events(adapter, prompt="Add numbers"))

    assert events == [
        TokenEvent(seq_id=0, ts=_expected_ts(0), content="Hello", index=0),
        ToolCallEvent(
            seq_id=1,
            ts=_expected_ts(1),
            call_id="tool-1",
            name="sum",
            args={"a": 1, "b": 3},
        ),
        ToolResultEvent(
            seq_id=2,
            ts=_expected_ts(2),
            call_id="tool-1",
            output="Sum is 4",
        ),
        FinalEvent(
            seq_id=3,
            ts=_expected_ts(3),
            output="Sum is 4",
            finish_reason="stop",
            usage={"total_tokens": 6},
        ),
    ]

    assert stream.closed


def test_template_adapter_wraps_provider_errors() -> None:
    class BrokenClient:
        def stream(self, **_: object) -> None:
            raise RuntimeError("boom")

    adapter = TemplateProviderAdapter(BrokenClient(), default_model="model")

    with pytest.raises(AdapterStreamError):
        adapter.stream("prompt")

    with pytest.raises(AdapterStreamError):
        asyncio.run(_collect_events(adapter, prompt="prompt"))
