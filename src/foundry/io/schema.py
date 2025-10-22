"""Core I/O schemas for Foundry agents."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Union

from pydantic import BaseModel, ConfigDict, Field

JSONPrimitive = Union[str, int, float, bool, None]
JSONValue = Union[JSONPrimitive, Dict[str, "JSONValue"], List["JSONValue"]]


class EventLevel(str, Enum):
    """Severity levels for :class:`SystemEvent`."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AgentInput(BaseModel):
    """Message presented to an agent for consumption."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str = Field(..., description="Unique identifier for this input message.")
    agent: str = Field(..., description="Name of the target agent.")
    received_at: datetime = Field(..., description="Timestamp at which the input became available.")
    payload: Dict[str, JSONValue] = Field(default_factory=dict, description="JSON-compatible payload delivered to the agent.")
    metadata: Dict[str, JSONValue] = Field(default_factory=dict, description="Arbitrary structured metadata.")


class AgentOutput(BaseModel):
    """Response produced by an agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str = Field(..., description="Unique identifier for this output message.")
    agent: str = Field(..., description="Name of the emitting agent.")
    created_at: datetime = Field(..., description="Timestamp when the output was produced.")
    payload: Dict[str, JSONValue] = Field(default_factory=dict, description="JSON-compatible payload emitted by the agent.")
    metadata: Dict[str, JSONValue] = Field(default_factory=dict, description="Supplemental metadata describing the output.")
    in_reply_to: str | None = Field(None, description="Identifier of the input that prompted this output, if any.")


class SystemEvent(BaseModel):
    """Telemetry emitted by the runtime or adapters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., description="Unique identifier for the event.")
    timestamp: datetime = Field(..., description="Timestamp for the event in UTC.")
    origin: str = Field(..., description="Component that emitted the event.")
    level: EventLevel = Field(default=EventLevel.INFO, description="Severity level of the event.")
    message: str = Field(..., description="Human-readable description of the event.")
    attributes: Dict[str, JSONValue] = Field(default_factory=dict, description="Structured data for diagnostics or analytics.")


class ExecutionTrace(BaseModel):
    """Trace tying inputs, outputs, and events together for observability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str = Field(..., description="Unique identifier for the trace.")
    agent: str = Field(..., description="Agent associated with this trace.")
    started_at: datetime = Field(..., description="Start timestamp for the trace.")
    completed_at: datetime | None = Field(None, description="Completion timestamp, if the trace has ended.")
    inputs: List[AgentInput] = Field(default_factory=list, description="Inputs consumed during the trace.")
    outputs: List[AgentOutput] = Field(default_factory=list, description="Outputs produced during the trace.")
    events: List[SystemEvent] = Field(default_factory=list, description="Runtime events observed in the trace.")
    metadata: Dict[str, JSONValue] = Field(default_factory=dict, description="Supplemental metadata for the trace.")


__all__ = [
    "AgentInput",
    "AgentOutput",
    "ExecutionTrace",
    "JSONValue",
    "SystemEvent",
    "EventLevel",
]
