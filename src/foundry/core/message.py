"""Message schema shared across adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import json
import math
from types import MappingProxyType
from typing import Any


class MessageRole(str, Enum):
    """Canonical role names supported by Foundry."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A provider tool/function invocation emitted by an assistant message."""

    id: str
    name: str
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            msg = "tool call id must be a non-empty string"
            raise ValueError(msg)
        if not isinstance(self.name, str) or not self.name:
            msg = "tool call name must be a non-empty string"
            raise ValueError(msg)
        if not isinstance(self.arguments, Mapping):
            msg = "tool call arguments must be a mapping"
            raise TypeError(msg)

        plain_arguments = _thaw_json_structure(dict(self.arguments))
        _ensure_json_compatible(plain_arguments, path="ToolCall.arguments")

        sanitized = json.loads(json.dumps(plain_arguments, allow_nan=False))
        frozen = _freeze_json_structure(sanitized)
        object.__setattr__(self, "arguments", frozen)


@dataclass(frozen=True, slots=True)
class Message:
    """A single message exchanged with a language model."""

    role: MessageRole
    content: str
    tool_calls: tuple[ToolCall, ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):  # pragma: no cover - defensive
            msg = "message content must be a string"
            raise TypeError(msg)

        normalized_tool_calls: tuple[ToolCall, ...] | None = None
        if self.tool_calls is not None:
            if not isinstance(self.tool_calls, Sequence) or isinstance(
                self.tool_calls, (str, bytes, bytearray)
            ):
                msg = "tool_calls must be a sequence of ToolCall instances"
                raise TypeError(msg)
            candidates = tuple(self.tool_calls)
            if not candidates:
                msg = "tool_calls cannot be empty"
                raise ValueError(msg)
            for call in candidates:
                if not isinstance(call, ToolCall):
                    msg = "tool_calls must contain ToolCall instances"
                    raise TypeError(msg)
            normalized_tool_calls = candidates
            object.__setattr__(self, "tool_calls", normalized_tool_calls)

        if self.content == "" and normalized_tool_calls is None:
            msg = "message content cannot be empty when no tool calls are present"
            raise ValueError(msg)


def _ensure_json_compatible(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, inner in value.items():
            if not isinstance(key, str) or not key:
                msg = f"{path} keys must be non-empty strings"
                raise TypeError(msg)
            _ensure_json_compatible(inner, path=f"{path}.{key}")
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _ensure_json_compatible(item, path=f"{path}[{index}]")
        return

    if isinstance(value, (bool, type(None), str)):
        return

    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            msg = f"{path} contains non-finite float values"
            raise ValueError(msg)
        return

    msg = f"{path} contains unsupported value type {type(value).__name__}"
    raise TypeError(msg)


def _freeze_json_structure(value: Any) -> Any:
    if isinstance(value, dict):
        frozen_dict = {key: _freeze_json_structure(inner) for key, inner in value.items()}
        return MappingProxyType(frozen_dict)

    if isinstance(value, list):
        return tuple(_freeze_json_structure(inner) for inner in value)

    return value


def _thaw_json_structure(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json_structure(inner) for key, inner in value.items()}

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_thaw_json_structure(inner) for inner in value]

    return value
