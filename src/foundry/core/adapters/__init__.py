"""Adapter interfaces and provider implementations."""

from __future__ import annotations

from .base import ModelAdapter
from .openai import OpenAIAdapter
from .stream import (
    BaseStreamIterator,
    FinalEvent,
    StreamEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from .utils import messages_to_openai, openai_to_messages

__all__ = [
    "ModelAdapter",
    "OpenAIAdapter",
    "BaseStreamIterator",
    "TokenEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "FinalEvent",
    "StreamEvent",
    "messages_to_openai",
    "openai_to_messages",
]
