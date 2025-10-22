"""Message schema shared across adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MessageRole(str, Enum):
    """Canonical role names supported by Foundry."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class Message:
    """A single message exchanged with a language model."""

    role: MessageRole
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):  # pragma: no cover - defensive
            msg = "message content must be a string"
            raise TypeError(msg)
        if not self.content:
            msg = "message content cannot be empty"
            raise ValueError(msg)
