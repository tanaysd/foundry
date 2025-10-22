from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from foundry.io.adapters.local import LocalIO
from foundry.io.schema import AgentInput, AgentOutput, EventLevel, SystemEvent


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def test_local_input_channel_reads_and_clears_messages() -> None:
    with TemporaryDirectory() as tmpdir:
        io = LocalIO(tmpdir)
        message = AgentInput(
            message_id="input-1",
            agent="alpha",
            received_at=_now(),
            payload={"task": "demo"},
        )
        io.push_input(message)

        read_message = io.inputs.read()
        assert read_message == message
        assert io.inputs.read() is None


def test_local_output_channel_persists_serialized_output() -> None:
    with TemporaryDirectory() as tmpdir:
        io = LocalIO(tmpdir)
        message = AgentOutput(
            message_id="output-1",
            agent="alpha",
            created_at=_now(),
            payload={"result": True},
        )

        io.outputs.write(message)

        output_files = sorted(Path(tmpdir, "outputs").glob("*.json"))
        assert len(output_files) == 1

        stored = json.loads(output_files[0].read_text(encoding="utf-8"))
        restored = AgentOutput.model_validate(stored)
        assert restored == message


def test_local_event_bus_roundtrip() -> None:
    with TemporaryDirectory() as tmpdir:
        io = LocalIO(tmpdir)
        event = SystemEvent(
            event_id="evt-1",
            timestamp=_now(),
            origin="runtime",
            level=EventLevel.WARNING,
            message="disk filling",
        )

        io.events.write(event)
        read_event = io.events.read()
        assert read_event == event
        assert io.events.read() is None


def test_flush_keeps_directories_intact() -> None:
    with TemporaryDirectory() as tmpdir:
        io = LocalIO(tmpdir)
        io.flush()

        assert Path(tmpdir, "inputs").exists()
        assert Path(tmpdir, "outputs").exists()
        assert Path(tmpdir, "events").exists()
