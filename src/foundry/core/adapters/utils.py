"""Pure conversion helpers shared by adapter implementations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..errors import AdapterError
from ..message import Message, MessageRole
from .toolbridge import normalize_tool_calls, tool_call_to_openai

_ROLE_VALUES = {role.value for role in MessageRole}
_ALLOWED_KEYS = {"role", "content", "tool_calls"}


def messages_to_openai(messages: Sequence[Message]) -> list[dict[str, Any]]:
    """Convert Foundry messages into the OpenAI Chat API format."""

    converted: list[dict[str, Any]] = []
    for message in messages:
        payload: dict[str, Any] = {
            "role": message.role.value,
            "content": message.content,
        }
        if message.tool_calls:
            payload["tool_calls"] = [tool_call_to_openai(call) for call in message.tool_calls]
        converted.append(payload)

    return converted


def openai_to_messages(payload: Sequence[Mapping[str, Any] | Any]) -> list[Message]:
    """Normalize OpenAI Chat API messages into Foundry's schema."""

    normalized: list[Message] = []
    for item in payload:
        mapping = _coerce_mapping(item)

        extra = set(mapping) - _ALLOWED_KEYS
        if extra:
            joined = ", ".join(sorted(extra))
            msg = f"unexpected fields in OpenAI payload: {joined}"
            raise AdapterError(msg)

        raw_role = mapping.get("role")
        if not isinstance(raw_role, str):
            msg = "message role must be a string"
            raise AdapterError(msg)
        normalized_role = raw_role.strip().lower()
        if normalized_role not in _ROLE_VALUES:
            msg = f"unsupported role '{raw_role}'"
            raise AdapterError(msg)

        raw_content = mapping.get("content", "")
        if raw_content is None:
            content = ""
        elif isinstance(raw_content, str):
            content = raw_content
        else:
            msg = "message content must be a string"
            raise AdapterError(msg)

        tool_calls_payload = mapping.get("tool_calls")
        tool_calls = None
        if tool_calls_payload is not None:
            if not isinstance(tool_calls_payload, Sequence) or isinstance(
                tool_calls_payload, (str, bytes, bytearray)
            ):
                msg = "tool_calls must be provided as a sequence"
                raise AdapterError(msg)
            tool_calls_tuple = normalize_tool_calls(tool_calls_payload)
            tool_calls = tool_calls_tuple or None

        if content == "" and tool_calls is None:
            msg = "message content cannot be empty"
            raise AdapterError(msg)

        normalized.append(
            Message(role=MessageRole(normalized_role), content=content, tool_calls=tool_calls)
        )

    return normalized


def _coerce_mapping(item: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(item, Mapping):
        return item

    if hasattr(item, "model_dump"):
        dump = getattr(item, "model_dump")
        result = dump()
        if isinstance(result, Mapping):
            return result

    msg = "OpenAI payload entries must be mappings"
    raise AdapterError(msg)
