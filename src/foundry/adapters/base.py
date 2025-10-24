"""Canonical adapter interface and streaming event definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class _EventBase:
    """Shared metadata for streaming events."""

    seq_id: int
    ts: datetime


@dataclass(frozen=True, slots=True)
class TokenEvent(_EventBase):
    """Incremental token emitted by the provider."""

    content: str
    index: int


@dataclass(frozen=True, slots=True)
class ToolCallEvent(_EventBase):
    """Canonical tool invocation emitted during streaming."""

    call_id: str
    name: str
    args: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResultEvent(_EventBase):
    """Result payload produced by a previously announced tool call."""

    call_id: str
    output: str


@dataclass(frozen=True, slots=True)
class FinalEvent(_EventBase):
    """Terminal event containing the consolidated assistant output."""

    output: str
    finish_reason: str | None = None
    usage: Mapping[str, int] | None = None


BaseEvent = TokenEvent | ToolCallEvent | ToolResultEvent | FinalEvent


@runtime_checkable
class BaseAdapter(Protocol):
    """Protocol implemented by all provider adapters."""

    def stream(self, prompt: str, /, **kwargs: Any) -> AsyncIterator[BaseEvent]:
        """Stream canonical events for the provided prompt."""


class AdapterStreamError(RuntimeError):
    """Error raised when provider streaming fails."""


__all__ = [
    "AdapterStreamError",
    "BaseAdapter",
    "BaseEvent",
    "FinalEvent",
    "TokenEvent",
    "ToolCallEvent",
    "ToolResultEvent",
]
