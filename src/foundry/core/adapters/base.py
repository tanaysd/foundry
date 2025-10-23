"""Adapter interface shared by provider implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from ..message import Message
from .stream import BaseStreamIterator


class ModelAdapter(ABC):
    """Abstract interface for provider-specific adapters."""

    @abstractmethod
    def generate(
        self,
        messages: Sequence[Message],
        /,
        *,
        tools: Any | None = None,
        stream: bool = False,
        **options: Any,
    ) -> Message:
        """Generate an assistant message from the provided conversation history."""

    @abstractmethod
    def stream(
        self,
        messages: Sequence[Message],
        /,
        *,
        tools: Any | None = None,
        **options: Any,
    ) -> BaseStreamIterator:
        """Return an async iterator that yields canonical streaming events."""
