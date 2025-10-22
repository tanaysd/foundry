"""OpenAI provider adapter (non-streaming, no tools)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..errors import AdapterError
from ..message import Message, MessageRole
from .base import ModelAdapter
from .utils import messages_to_openai, openai_to_messages


class OpenAIAdapter(ModelAdapter):
    """Translate Foundry messages to OpenAI's chat completion API."""

    def __init__(
        self,
        client: Any,
        *,
        default_model: str | None = None,
        default_params: Mapping[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._default_model = default_model
        self._default_params = dict(default_params or {})

        if "model" in self._default_params and self._default_model is None:
            model_value = self._default_params.pop("model")
            self._default_model = str(model_value)

        reserved = {"messages", "stream"}
        conflict = reserved.intersection(self._default_params)
        if conflict:
            joined = ", ".join(sorted(conflict))
            msg = f"default parameters cannot include reserved keys: {joined}"
            raise ValueError(msg)

    def generate(
        self,
        messages: Sequence[Message],
        /,
        *,
        tools: Any | None = None,
        stream: bool = False,
        **options: Any,
    ) -> Message:
        if tools not in (None, [], {}):
            msg = "tool calling is not supported"
            raise AdapterError(msg)
        if stream:
            msg = "streaming is not supported"
            raise AdapterError(msg)
        if not messages:
            msg = "at least one message is required"
            raise AdapterError(msg)

        model_name = self._resolve_model(options)

        request_payload = self._build_payload(messages, model_name, options)

        try:
            response = self._client.chat.completions.create(**request_payload)
        except Exception as exc:  # pragma: no cover - transport errors
            msg = "OpenAI client call failed"
            raise AdapterError(msg) from exc

        choice = self._extract_first_choice(response)
        message_payload = self._extract_choice_message(choice)

        assistant_messages = openai_to_messages([message_payload])
        assistant = assistant_messages[0]
        if assistant.role is not MessageRole.ASSISTANT:
            msg = "OpenAI returned a non-assistant message"
            raise AdapterError(msg)
        return assistant

    def _resolve_model(self, options: dict[str, Any]) -> str:
        model_option = options.pop("model", None)
        model_name = model_option or self._default_model
        if not model_name:
            msg = "a model name must be provided"
            raise AdapterError(msg)
        return str(model_name)

    def _build_payload(
        self,
        messages: Sequence[Message],
        model_name: str,
        options: Mapping[str, Any],
    ) -> dict[str, Any]:
        request_payload: dict[str, Any] = {"model": model_name, **self._default_params}
        for key, value in options.items():
            if key in {"messages", "stream"}:
                msg = f"option '{key}' is managed by the adapter"
                raise AdapterError(msg)
            request_payload[key] = value

        request_payload.setdefault("temperature", 0)
        request_payload["messages"] = messages_to_openai(messages)
        return request_payload

    def _extract_first_choice(self, response: Any) -> Any:
        choices = None
        if isinstance(response, Mapping):
            choices = response.get("choices")
        else:
            choices = getattr(response, "choices", None)

        if not isinstance(choices, Sequence) or not choices:
            msg = "OpenAI response missing choices"
            raise AdapterError(msg)
        return choices[0]

    def _extract_choice_message(self, choice: Any) -> Mapping[str, Any]:
        message_payload: Any
        if isinstance(choice, Mapping):
            message_payload = choice.get("message")
        else:
            message_payload = getattr(choice, "message", None)

        if message_payload is None:
            msg = "OpenAI choice missing message payload"
            raise AdapterError(msg)

        if isinstance(message_payload, Message):
            return {"role": message_payload.role.value, "content": message_payload.content}

        if hasattr(message_payload, "model_dump"):
            dump = getattr(message_payload, "model_dump")
            dumped = dump()
            if not isinstance(dumped, Mapping):
                msg = "model_dump() must return a mapping"
                raise AdapterError(msg)
            return dumped

        if isinstance(message_payload, Mapping):
            return message_payload

        msg = "unsupported OpenAI message payload type"
        raise AdapterError(msg)
