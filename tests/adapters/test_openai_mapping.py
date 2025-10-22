from __future__ import annotations

import pytest

from foundry.core import AdapterError, Message, MessageRole
from foundry.core.adapters.utils import messages_to_openai, openai_to_messages


def test_round_trip_preserves_roles_and_content() -> None:
    messages = [
        Message(role=MessageRole.SYSTEM, content="Configure"),
        Message(role=MessageRole.USER, content="Hello"),
        Message(role=MessageRole.ASSISTANT, content="Hi!"),
    ]

    payload = messages_to_openai(messages)
    assert payload == [
        {"role": "system", "content": "Configure"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]

    normalized = openai_to_messages(payload)
    assert normalized == messages


def test_openai_to_messages_rejects_unknown_role() -> None:
    with pytest.raises(AdapterError):
        openai_to_messages([
            {"role": "tool", "content": "noop"},
        ])


def test_openai_to_messages_rejects_empty_content() -> None:
    with pytest.raises(AdapterError):
        openai_to_messages([
            {"role": "user", "content": ""},
        ])


def test_openai_to_messages_rejects_extra_fields() -> None:
    with pytest.raises(AdapterError):
        openai_to_messages([
            {"role": "assistant", "content": "hello", "foo": "bar"},
        ])
