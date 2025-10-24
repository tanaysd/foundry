"""State primitives tracked while streaming model responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from foundry.core.adapters.stream import TokenEvent, ToolCallEvent


@dataclass(slots=True)
class AgentState:
    """Aggregated runtime state for a single agent session."""

    memory: list[str] = field(default_factory=list)
    last_tool: ToolCallEvent | None = None
    tokens: list[TokenEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> AgentState:
        """Return an immutable copy of the current runtime state."""

        # Tool call events and token events are effectively immutable dataclasses,
        # so a shallow copy is sufficient for them. Metadata may contain nested
        # dictionaries, therefore we perform a deep copy there.
        from copy import deepcopy

        return AgentState(
            memory=list(self.memory),
            last_tool=self.last_tool,
            tokens=list(self.tokens),
            metadata=deepcopy(self.metadata),
        )
