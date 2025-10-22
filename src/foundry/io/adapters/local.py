"""Local filesystem-backed I/O adapters for testing and development."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional, cast
from uuid import uuid4

from ..interfaces import EventBus, InputChannel, OutputChannel
from ..schema import AgentInput, AgentOutput, JSONValue, SystemEvent


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_payload(directory: Path, payload: dict[str, JSONValue], prefix: str) -> Path:
    _ensure_directory(directory)
    file_path = directory / f"{prefix}-{uuid4().hex}.json"
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return file_path


def _next_json_file(directory: Path) -> Optional[Path]:
    if not directory.exists():
        return None
    json_files = sorted(p for p in directory.iterdir() if p.suffix == ".json")
    if not json_files:
        return None
    return json_files[0]


class LocalInputChannel(InputChannel):
    """Read agent inputs from JSON files within a directory."""

    def __init__(self, directory: Path | str):
        self._directory = Path(directory)
        _ensure_directory(self._directory)

    @property
    def directory(self) -> Path:
        """Directory backing this channel."""

        return self._directory

    def read(self) -> Optional[AgentInput]:
        candidate = _next_json_file(self._directory)
        if candidate is None:
            return None
        payload = candidate.read_text(encoding="utf-8")
        message = cast(AgentInput, AgentInput.model_validate_json(payload))
        candidate.unlink()
        return message

    def flush(self) -> None:
        _ensure_directory(self._directory)


class LocalOutputChannel(OutputChannel):
    """Persist agent outputs as JSON files on disk."""

    def __init__(self, directory: Path | str):
        self._directory = Path(directory)
        _ensure_directory(self._directory)

    @property
    def directory(self) -> Path:
        return self._directory

    def write(self, message: AgentOutput) -> None:
        payload = cast(dict[str, JSONValue], message.model_dump(mode="json"))
        _write_payload(self._directory, payload, prefix="output")

    def flush(self) -> None:
        _ensure_directory(self._directory)


class LocalEventBus(EventBus):
    """Filesystem-backed event bus for deterministic tests."""

    def __init__(self, directory: Path | str):
        self._directory = Path(directory)
        _ensure_directory(self._directory)

    @property
    def directory(self) -> Path:
        return self._directory

    def read(self) -> Optional[SystemEvent]:
        candidate = _next_json_file(self._directory)
        if candidate is None:
            return None
        payload = candidate.read_text(encoding="utf-8")
        event = cast(SystemEvent, SystemEvent.model_validate_json(payload))
        candidate.unlink()
        return event

    def write(self, event: SystemEvent) -> None:
        payload = cast(dict[str, JSONValue], event.model_dump(mode="json"))
        _write_payload(self._directory, payload, prefix="event")

    def flush(self) -> None:
        _ensure_directory(self._directory)


class LocalIO:
    """Convenience wrapper bundling local adapters together."""

    def __init__(self, base_path: Path | str | None = None):
        if base_path is None:
            base = Path(tempfile.mkdtemp(prefix="foundry-io-"))
        else:
            base = Path(base_path)
            _ensure_directory(base)
        self.base_path = base
        self.inputs = LocalInputChannel(base / "inputs")
        self.outputs = LocalOutputChannel(base / "outputs")
        self.events = LocalEventBus(base / "events")

    def push_input(self, message: AgentInput) -> Path:
        """Inject an :class:`AgentInput` into the input queue."""

        payload = cast(dict[str, JSONValue], message.model_dump(mode="json"))
        return _write_payload(self.inputs.directory, payload, prefix="input")

    def record_event(self, event: SystemEvent) -> Path:
        """Persist a :class:`SystemEvent` without exposing adapter internals."""

        payload = cast(dict[str, JSONValue], event.model_dump(mode="json"))
        return _write_payload(self.events.directory, payload, prefix="event")

    def flush(self) -> None:
        """Flush all underlying adapters."""

        self.inputs.flush()
        self.outputs.flush()
        self.events.flush()


__all__ = [
    "LocalEventBus",
    "LocalIO",
    "LocalInputChannel",
    "LocalOutputChannel",
]
