"""Adapter interfaces and provider implementations."""

from __future__ import annotations

from .base import ModelAdapter
from .openai import OpenAIAdapter
from .utils import messages_to_openai, openai_to_messages

__all__ = [
    "ModelAdapter",
    "OpenAIAdapter",
    "messages_to_openai",
    "openai_to_messages",
]
