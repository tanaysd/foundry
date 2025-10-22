"""Abstract interfaces for Foundry I/O components."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .schema import AgentInput, AgentOutput, SystemEvent


class InputChannel(ABC):
    """Source of :class:`AgentInput` messages."""

    @abstractmethod
    def read(self) -> Optional[AgentInput]:
        """Retrieve the next available input message."""

    @abstractmethod
    def flush(self) -> None:
        """Clear any buffered state or pending messages."""


class OutputChannel(ABC):
    """Sink for :class:`AgentOutput` messages."""

    @abstractmethod
    def write(self, message: AgentOutput) -> None:
        """Persist an output message."""

    @abstractmethod
    def flush(self) -> None:
        """Ensure all buffered messages are visible to consumers."""


class EventBus(ABC):
    """Transport for :class:`SystemEvent` telemetry."""

    @abstractmethod
    def read(self) -> Optional[SystemEvent]:
        """Retrieve the next available event, if any."""

    @abstractmethod
    def write(self, event: SystemEvent) -> None:
        """Publish a new event to the bus."""

    @abstractmethod
    def flush(self) -> None:
        """Flush buffered events and release resources."""


__all__ = ["EventBus", "InputChannel", "OutputChannel"]
