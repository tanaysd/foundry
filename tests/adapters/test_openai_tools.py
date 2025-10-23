from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from foundry.core import AdapterError, Message, MessageRole, ToolCall
from foundry.core.adapters.openai import OpenAIAdapter
from foundry.core.adapters.toolbridge import (
    ToolSpec,
    normalize_tool_calls,
    tool_specs_to_openai,
)
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


def build_weather_spec() -> ToolSpec:
    return ToolSpec(
        name="get_weather",
        description="Return weather observations for a location",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name to resolve",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "lat": {"type": "number"},
                        "lon": {"type": "number"},
                    },
                    "required": ["lat", "lon"],
                },
            },
            "required": ["location"],
        },
    )


def test_tool_spec_mapping_includes_nested_properties() -> None:
    spec = build_weather_spec()

    tools_payload = tool_specs_to_openai([spec])

    assert tools_payload == [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Return weather observations for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name to resolve",
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                        },
                        "metadata": {
                            "type": "object",
                            "properties": {
                                "lat": {"type": "number"},
                                "lon": {"type": "number"},
                            },
                            "required": ["lat", "lon"],
                        },
                    },
                    "required": ["location"],
                },
            },
        }
    ]


def test_tool_spec_validation_rejects_invalid_schema() -> None:
    with pytest.raises(AdapterError):
        ToolSpec(
            name="bad-tool",
            parameters={"type": "array", "items": {}},
        )


def test_tool_spec_validation_rejects_duplicate_names() -> None:
    spec = build_weather_spec()

    with pytest.raises(AdapterError):
        tool_specs_to_openai([spec, spec])


def test_normalize_tool_calls_parses_arguments() -> None:
    payload = [
        {
            "id": "call_abc",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": json.dumps(
                    {
                        "location": "Berlin",
                        "unit": "celsius",
                        "metadata": {"lat": 52.5, "lon": 13.4},
                    },
                    allow_nan=False,
                ),
            },
        }
    ]

    [tool_call] = normalize_tool_calls(payload)

    assert tool_call.id == "call_abc"
    assert tool_call.name == "get_weather"
    assert tool_call.arguments["location"] == "Berlin"
    assert tool_call.arguments["metadata"]["lat"] == 52.5


def test_normalize_tool_calls_rejects_invalid_json() -> None:
    payload = [
        {
            "id": "call_bad",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": "{not json}",
            },
        }
    ]

    with pytest.raises(AdapterError):
        normalize_tool_calls(payload)


def test_generate_returns_message_with_tool_calls() -> None:
    spec = build_weather_spec()
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
                                    {
                                        "location": "Paris",
                                        "unit": "celsius",
                                    },
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

    prompt = [
        Message(role=MessageRole.SYSTEM, content="Weather agent"),
        Message(role=MessageRole.USER, content="Temperature in Paris?"),
    ]

    assistant = adapter.generate(prompt, tools=[spec])

    assert assistant.content == ""
    assert assistant.tool_calls is not None
    [tool_call] = assistant.tool_calls
    assert tool_call.id == "call_weather"
    assert tool_call.arguments["location"] == "Paris"

    [call] = client.completions.calls
    assert "tools" in call
    assert call["tools"] == tool_specs_to_openai([spec])


def test_generate_rejects_invalid_tool_response() -> None:
    spec = build_weather_spec()
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
                                "arguments": "not json",
                            },
                        }
                    ],
                }
            }
        ]
    }
    client = build_fake_client(response)
    adapter = OpenAIAdapter(client, default_model="gpt-4o-mini")

    prompt = [Message(role=MessageRole.USER, content="Temperature in Paris?")]

    with pytest.raises(AdapterError):
        adapter.generate(prompt, tools=[spec])


def test_messages_to_openai_includes_tool_calls() -> None:
    tool_call = ToolCall(
        id="call_1",
        name="get_weather",
        arguments={"location": "Lisbon", "unit": "fahrenheit"},
    )
    message = Message(
        role=MessageRole.ASSISTANT,
        content="",
        tool_calls=(tool_call,),
    )

    payload = messages_to_openai([message])

    assert payload == [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": json.dumps(
                            {"location": "Lisbon", "unit": "fahrenheit"},
                            allow_nan=False,
                        ),
                    },
                }
            ],
        }
    ]
