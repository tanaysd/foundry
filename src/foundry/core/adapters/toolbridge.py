"""Mapping helpers between Foundry tool specs and provider schemas."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import math
import re
from types import MappingProxyType
from typing import Any

from ..errors import AdapterError
from ..message import ToolCall

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Foundry's canonical tool/function description."""

    name: str
    parameters: Mapping[str, Any]
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _NAME_PATTERN.fullmatch(self.name):
            msg = "tool name must match ^[a-zA-Z0-9_-]{1,64}$"
            raise AdapterError(msg)

        normalized_description: str | None = None
        if self.description is not None:
            if not isinstance(self.description, str):
                msg = "tool description must be a string when provided"
                raise AdapterError(msg)
            stripped = self.description.strip()
            if not stripped:
                msg = "tool description cannot be empty"
                raise AdapterError(msg)
            normalized_description = stripped

        if not isinstance(self.parameters, Mapping):
            msg = "tool parameters must be a mapping"
            raise AdapterError(msg)

        raw_parameters = dict(self.parameters)
        _ensure_json_compatible(raw_parameters, path=f"ToolSpec('{self.name}').parameters")

        try:
            sanitized = json.loads(json.dumps(raw_parameters, allow_nan=False))
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            msg = "tool parameters must be JSON serializable"
            raise AdapterError(msg) from exc

        if sanitized.get("type") != "object":
            msg = "tool parameters must describe a JSON object"
            raise AdapterError(msg)

        properties = sanitized.get("properties")
        if properties is None or not isinstance(properties, dict):
            msg = "tool parameters must include an object 'properties' mapping"
            raise AdapterError(msg)

        for key in properties:
            if not isinstance(key, str) or not key:
                msg = "tool parameter names must be non-empty strings"
                raise AdapterError(msg)

        required = sanitized.get("required")
        if required is not None:
            if not isinstance(required, list):
                msg = "tool parameter 'required' must be a list of strings"
                raise AdapterError(msg)
            for index, item in enumerate(required):
                if not isinstance(item, str) or not item:
                    msg = f"required parameter names must be non-empty strings (index {index})"
                    raise AdapterError(msg)
                if item not in properties:
                    msg = f"required parameter '{item}' is not defined"
                    raise AdapterError(msg)

        frozen_parameters = _freeze_json_structure(sanitized)

        if normalized_description is not None:
            object.__setattr__(self, "description", normalized_description)
        object.__setattr__(self, "parameters", frozen_parameters)


def tool_specs_to_openai(tool_specs: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    """Convert Foundry tool specifications to OpenAI's chat tools schema."""

    if isinstance(tool_specs, (str, bytes, bytearray)):
        msg = "tools must be provided as a sequence of ToolSpec instances"
        raise AdapterError(msg)

    tools_list = list(tool_specs)
    normalized_tools: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for index, spec in enumerate(tools_list):
        if not isinstance(spec, ToolSpec):
            msg = f"tools[{index}] must be a ToolSpec"
            raise AdapterError(msg)
        if spec.name in seen_names:
            msg = f"duplicate tool name '{spec.name}'"
            raise AdapterError(msg)
        seen_names.add(spec.name)

        function_payload: dict[str, Any] = {
            "name": spec.name,
            "parameters": _thaw_json_structure(spec.parameters),
        }
        if spec.description is not None:
            function_payload["description"] = spec.description

        normalized_tools.append({"type": "function", "function": function_payload})

    return normalized_tools


def normalize_tool_calls(tool_calls: Sequence[Mapping[str, Any] | Any]) -> tuple[ToolCall, ...]:
    """Normalize provider tool call payloads into Foundry ToolCall instances."""

    if isinstance(tool_calls, (str, bytes, bytearray)):
        msg = "tool_calls payload must be a sequence"
        raise AdapterError(msg)

    normalized: list[ToolCall] = []
    for index, item in enumerate(tool_calls):
        mapping = _coerce_mapping(item, path=f"tool_calls[{index}]")

        call_id = mapping.get("id")
        if not isinstance(call_id, str) or not call_id:
            msg = f"tool call at index {index} is missing a valid id"
            raise AdapterError(msg)

        call_type = mapping.get("type")
        if call_type != "function":
            msg = f"tool call at index {index} must have type 'function'"
            raise AdapterError(msg)

        function_payload = mapping.get("function")
        function_mapping = _coerce_mapping(function_payload, path=f"tool_calls[{index}].function")

        name = function_mapping.get("name")
        if not isinstance(name, str) or not name:
            msg = f"tool call at index {index} is missing a valid function name"
            raise AdapterError(msg)

        raw_arguments = function_mapping.get("arguments", "{}")
        arguments_mapping = _coerce_arguments(raw_arguments, path=f"tool_calls[{index}].function.arguments")

        normalized.append(ToolCall(id=call_id, name=name, arguments=arguments_mapping))

    return tuple(normalized)


def tool_call_to_openai(tool_call: ToolCall) -> dict[str, Any]:
    """Convert a Foundry ToolCall into the provider representation."""

    if not isinstance(tool_call, ToolCall):  # pragma: no cover - defensive
        msg = "tool_call must be a ToolCall instance"
        raise AdapterError(msg)

    thawed_arguments = _thaw_json_structure(tool_call.arguments)
    try:
        arguments_json = json.dumps(thawed_arguments, allow_nan=False)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        msg = "tool call arguments must be JSON serializable"
        raise AdapterError(msg) from exc

    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.name,
            "arguments": arguments_json,
        },
    }


def _coerce_mapping(value: Mapping[str, Any] | Any, *, path: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value

    if hasattr(value, "model_dump"):
        dump = getattr(value, "model_dump")
        dumped = dump()
        if isinstance(dumped, Mapping):
            return dumped

    msg = f"{path} must be a mapping"
    raise AdapterError(msg)


def _coerce_arguments(raw: Any, *, path: str) -> Mapping[str, Any]:
    if isinstance(raw, Mapping):
        mapping = dict(raw)
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            msg = f"{path} must contain valid JSON"
            raise AdapterError(msg) from exc
        if not isinstance(parsed, Mapping):
            msg = f"{path} must decode to a JSON object"
            raise AdapterError(msg)
        mapping = dict(parsed)
    else:
        msg = f"{path} must be a mapping or JSON string"
        raise AdapterError(msg)

    _ensure_json_compatible(mapping, path=path)

    try:
        sanitized = json.loads(json.dumps(mapping, allow_nan=False))
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        msg = f"{path} must contain JSON serializable data"
        raise AdapterError(msg) from exc

    if not isinstance(sanitized, dict):  # pragma: no cover - defensive
        msg = f"{path} must decode to a JSON object"
        raise AdapterError(msg)

    return _freeze_json_structure(sanitized)


def _ensure_json_compatible(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, inner in value.items():
            if not isinstance(key, str) or not key:
                msg = f"{path} keys must be non-empty strings"
                raise AdapterError(msg)
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
            raise AdapterError(msg)
        return

    msg = f"{path} contains unsupported value type {type(value).__name__}"
    raise AdapterError(msg)


def _freeze_json_structure(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):  # pragma: no cover - defensive
        msg = "expected a dictionary to freeze"
        raise AdapterError(msg)

    frozen_dict = {key: _freeze_nested_json(inner) for key, inner in value.items()}
    return MappingProxyType(frozen_dict)


def _freeze_nested_json(value: Any) -> Any:
    if isinstance(value, dict):
        nested = {key: _freeze_nested_json(inner) for key, inner in value.items()}
        return MappingProxyType(nested)

    if isinstance(value, list):
        return tuple(_freeze_nested_json(inner) for inner in value)

    return value


def _thaw_json_structure(value: Mapping[str, Any] | Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json_structure(inner) for key, inner in value.items()}

    if isinstance(value, tuple):
        return [_thaw_json_structure(inner) for inner in value]

    return value
