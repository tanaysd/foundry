from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from foundry.io.schema import (
    AgentInput,
    AgentOutput,
    EventLevel,
    ExecutionTrace,
    SystemEvent,
)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def test_agent_input_roundtrip() -> None:
    message = AgentInput(
        message_id="input-1",
        agent="alpha",
        received_at=_now(),
        payload={"command": "run", "args": ["--foo", 1]},
        metadata={"priority": "high"},
    )

    dumped = json.dumps(message.model_dump(mode="json"))
    restored = AgentInput.model_validate_json(dumped)

    assert restored == message


def test_agent_input_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AgentInput.model_validate(
            {
                "message_id": "bad",
                "agent": "beta",
                "received_at": _now(),
                "payload": {},
                "metadata": {},
                "unknown": "field",
            }
        )


def test_system_event_defaults() -> None:
    event = SystemEvent(
        event_id="evt-1",
        timestamp=_now(),
        origin="runtime",
        message="adapter initialised",
    )

    assert event.level is EventLevel.INFO
    assert event.attributes == {}


def test_execution_trace_relationships() -> None:
    agent = "alpha"
    input_msg = AgentInput(
        message_id="input-1",
        agent=agent,
        received_at=_now(),
        payload={"command": "plan"},
    )
    output_msg = AgentOutput(
        message_id="output-1",
        agent=agent,
        created_at=_now(),
        payload={"result": "ok"},
        in_reply_to=input_msg.message_id,
    )
    event = SystemEvent(
        event_id="evt-2",
        timestamp=_now(),
        origin="runtime",
        level=EventLevel.DEBUG,
        message="processing",
        attributes={"step": 1},
    )

    trace = ExecutionTrace(
        trace_id="trace-1",
        agent=agent,
        started_at=_now(),
        completed_at=None,
        inputs=[input_msg],
        outputs=[output_msg],
        events=[event],
        metadata={"session": "abc"},
    )

    trace_json = trace.model_dump(mode="json")
    restored = ExecutionTrace.model_validate(trace_json)

    assert restored.inputs[0].message_id == input_msg.message_id
    assert restored.outputs[0].in_reply_to == input_msg.message_id
    assert restored.events[0].level is EventLevel.DEBUG


def test_agent_output_requires_timestamp() -> None:
    with pytest.raises(ValidationError):
        AgentOutput.model_validate(
            {
                "message_id": "output-missing",
                "agent": "gamma",
                "payload": {},
            }
        )
