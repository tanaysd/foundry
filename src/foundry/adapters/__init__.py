"""Provider adapter interfaces and implementations."""

from .base import (
    BaseAdapter,
    BaseEvent,
    FinalEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    AdapterStreamError,
)
from .openai_adapter import OpenAIAdapter
from .template_provider_adapter import TemplateProviderAdapter, TemplateProviderChunk

__all__ = [
    "AdapterStreamError",
    "BaseAdapter",
    "BaseEvent",
    "FinalEvent",
    "OpenAIAdapter",
    "TemplateProviderAdapter",
    "TemplateProviderChunk",
    "TokenEvent",
    "ToolCallEvent",
    "ToolResultEvent",
]
