from __future__ import annotations

from types import SimpleNamespace

import pytest

from foundry.core import AdapterError, Message, MessageRole
from foundry.core.adapters.openai import OpenAIAdapter


class FakeCompletions:
    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self._response


def build_fake_client(response: object) -> SimpleNamespace:
    completions = FakeCompletions(response)
    chat = SimpleNamespace(completions=completions)
    return SimpleNamespace(chat=chat, completions=completions)


def test_generate_returns_normalized_assistant_message() -> None:
    response = {
        "choices": [
            {"message": {"role": "assistant", "content": "All systems nominal."}},
        ]
    }
    client = build_fake_client(response)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    prompt = [
        Message(role=MessageRole.SYSTEM, content="Monitor"),
        Message(role=MessageRole.USER, content="Status?"),
    ]

    result = adapter.generate(prompt)

    assert result.role is MessageRole.ASSISTANT
    assert result.content == "All systems nominal."

    [call] = client.completions.calls
    assert call["model"] == "gpt-4o-mini"
    assert call["temperature"] == 0
    assert call["messages"] == [
        {"role": "system", "content": "Monitor"},
        {"role": "user", "content": "Status?"},
    ]


def test_generate_requires_model_name() -> None:
    response = {"choices": []}
    client = build_fake_client(response)
    adapter = OpenAIAdapter(client)

    with pytest.raises(AdapterError):
        adapter.generate([Message(role=MessageRole.USER, content="Hi")])


def test_generate_rejects_empty_messages() -> None:
    client = build_fake_client({"choices": []})
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    with pytest.raises(AdapterError):
        adapter.generate([])


def test_generate_rejects_streaming_option() -> None:
    response = {
        "choices": [
            {"message": {"role": "assistant", "content": "noop"}},
        ]
    }
    client = build_fake_client(response)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")
    prompt = [Message(role=MessageRole.USER, content="Hello")]

    with pytest.raises(AdapterError):
        adapter.generate(prompt, stream=True)


def test_generate_rejects_reserved_options() -> None:
    response = {
        "choices": [
            {"message": {"role": "assistant", "content": "noop"}},
        ]
    }
    client = build_fake_client(response)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    prompt = [Message(role=MessageRole.USER, content="Hello")]

    with pytest.raises(AdapterError):
        adapter.generate(prompt, messages=[])


def test_generate_handles_missing_message_payload() -> None:
    response = {
        "choices": [
            {"index": 0},
        ]
    }
    client = build_fake_client(response)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    with pytest.raises(AdapterError):
        adapter.generate([Message(role=MessageRole.USER, content="Hello")])
