"""Pure conversion helpers shared by adapter implementations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..errors import AdapterError
from ..message import Message, MessageRole

_ROLE_VALUES = {role.value for role in MessageRole}
_ALLOWED_KEYS = {"role", "content"}


def messages_to_openai(messages: Sequence[Message]) -> list[dict[str, str]]:
    """Convert Foundry messages into the OpenAI Chat API format."""

    return [{"role": message.role.value, "content": message.content} for message in messages]


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

        content = mapping.get("content")
        if not isinstance(content, str):
            msg = "message content must be a string"
            raise AdapterError(msg)
        if content == "":
            msg = "message content cannot be empty"
            raise AdapterError(msg)

        normalized.append(Message(role=MessageRole(normalized_role), content=content))

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
