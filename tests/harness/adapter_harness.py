"""Reusable harness utilities for validating streaming adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from foundry.core.adapters.base import ModelAdapter
from foundry.core.adapters.stream import (
    FinalEvent as _FinalEvent,
    StreamEvent,
    TokenEvent as _TokenEvent,
    ToolCallEvent as _ToolCallEvent,
    ToolResultEvent as _ToolResultEvent,
    replay_stream,
)
from foundry.core.message import Message, MessageRole

EventType = Literal["token", "tool_call", "tool_result", "final"]


@dataclass(slots=True)
class BaseEvent:
    """Canonical representation of adapter streaming events."""

    type: EventType
    content: str | None = None
    index: int | None = None
    id: str | None = None
    name: str | None = None
    args_fragment: str | None = None
    is_final: bool | None = None
    output: str | None = None
    total_tokens: int | None = None

    @classmethod
    def token(cls, *, content: str, index: int) -> "BaseEvent":
        return cls("token", content=content, index=index)

    @classmethod
    def tool_call(
        cls,
        *,
        id: str,
        name: str,
        args_fragment: str,
        is_final: bool,
    ) -> "BaseEvent":
        return cls(
            "tool_call",
            id=id,
            name=name,
            args_fragment=args_fragment,
            is_final=is_final,
        )

    @classmethod
    def tool_result(cls, *, id: str, output: str) -> "BaseEvent":
        return cls("tool_result", id=id, output=output)

    @classmethod
    def final(
        cls,
        *,
        output: str,
        total_tokens: int | None = None,
    ) -> "BaseEvent":
        return cls("final", output=output, total_tokens=total_tokens)

    @classmethod
    def from_stream_event(cls, event: StreamEvent) -> "BaseEvent":
        if isinstance(event, _TokenEvent):
            return cls.token(content=event.content, index=event.index)
        if isinstance(event, _ToolCallEvent):
            return cls.tool_call(
                id=event.id,
                name=event.name,
                args_fragment=event.args_fragment,
                is_final=event.is_final,
            )
        if isinstance(event, _ToolResultEvent):
            return cls.tool_result(id=event.id, output=event.output)
        if isinstance(event, _FinalEvent):
            return cls.final(output=event.output, total_tokens=event.total_tokens)
        msg = f"unsupported stream event type: {type(event).__name__}"
        raise TypeError(msg)


async def collect_async(
    adapter: ModelAdapter,
    *,
    prompt: str | None = None,
    messages: Sequence[Message] | None = None,
    system_prompt: str | None = "Harness system",
    tools: Sequence[Any] | None = None,
) -> list[BaseEvent]:
    """Collect streaming events from an adapter using the provided prompt."""

    normalized = _resolve_messages(prompt=prompt, messages=messages, system_prompt=system_prompt)
    iterator = adapter.stream(normalized, tools=tools)
    events = await replay_stream(iterator)
    return [BaseEvent.from_stream_event(event) for event in events]


def collect(
    adapter: ModelAdapter,
    *,
    prompt: str | None = None,
    messages: Sequence[Message] | None = None,
    system_prompt: str | None = "Harness system",
    tools: Sequence[Any] | None = None,
) -> list[BaseEvent]:
    """Synchronous wrapper around :func:`collect_async`."""

    return asyncio.run(
        collect_async(
            adapter,
            prompt=prompt,
            messages=messages,
            system_prompt=system_prompt,
            tools=tools,
        )
    )


def _resolve_messages(
    *,
    prompt: str | None,
    messages: Sequence[Message] | None,
    system_prompt: str | None,
) -> list[Message]:
    if prompt is not None and messages is not None:
        msg = "provide either 'prompt' or 'messages', not both"
        raise ValueError(msg)

    if prompt is None and messages is None:
        msg = "either 'prompt' or 'messages' must be provided"
        raise ValueError(msg)

    if prompt is not None:
        resolved: list[Message] = []
        if system_prompt is not None:
            resolved.append(Message(role=MessageRole.SYSTEM, content=system_prompt))
        resolved.append(Message(role=MessageRole.USER, content=prompt))
        return resolved

    resolved = list(messages or ())
    for index, message in enumerate(resolved):
        if not isinstance(message, Message):
            msg = f"messages[{index}] must be a Message instance"
            raise TypeError(msg)
    return resolved


__all__ = ["BaseEvent", "collect", "collect_async"]
