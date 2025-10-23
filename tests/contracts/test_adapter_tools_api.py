from __future__ import annotations

import json
from types import SimpleNamespace

from foundry.core import Message, MessageRole
from foundry.core.adapters.openai import OpenAIAdapter
from foundry.core.adapters.toolbridge import ToolSpec, normalize_tool_calls, tool_specs_to_openai
from foundry.core.adapters.utils import messages_to_openai


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


def build_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="get_weather",
            description="Lookup the weather for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        ),
        ToolSpec(
            name="get_time",
            description="Return current time for a timezone",
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {"type": "string"},
                },
                "required": ["timezone"],
            },
        ),
    ]


def test_openai_tool_normalization_matches_bridge() -> None:
    specs = build_specs()
    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_weather",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": json.dumps(
                                    {"location": "Rome", "unit": "celsius"},
                                    allow_nan=False,
                                ),
                            },
                        }
                    ],
                }
            }
        ]
    }
    client = build_fake_client(response)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    prompt = [Message(role=MessageRole.USER, content="Weather in Rome?")]

    assistant = adapter.generate(prompt, tools=specs)

    assert assistant.tool_calls is not None
    expected_calls = normalize_tool_calls(response["choices"][0]["message"]["tool_calls"])
    assert assistant.tool_calls == expected_calls

    round_trip_payload = messages_to_openai([assistant])[0]["tool_calls"]
    assert normalize_tool_calls(round_trip_payload) == expected_calls

    [call] = client.completions.calls
    assert call["tools"] == tool_specs_to_openai(specs)
