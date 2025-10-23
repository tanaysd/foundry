"""Core data structures and adapter interfaces for Foundry."""

from __future__ import annotations

from .errors import AdapterError
from .message import Message, MessageRole, ToolCall
from .adapters.toolbridge import ToolSpec

__all__ = [
    "AdapterError",
    "Message",
    "MessageRole",
    "ToolCall",
    "ToolSpec",
]
