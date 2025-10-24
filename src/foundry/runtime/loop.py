"""Async runtime loop coordinating adapters, events, and transcripts."""

from __future__ import annotations

import inspect
import logging
from asyncio import CancelledError
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from foundry.core.adapters import ModelAdapter
from foundry.core.adapters.stream import (
    BaseStreamIterator,
    FinalEvent,
    StreamEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from foundry.core.message import Message

from .state import AgentState


LOGGER = logging.getLogger(__name__)


class SessionTranscript:
    """Buffer of streaming events and state snapshots for deterministic replay."""

    def __init__(self) -> None:
        self._events: list[StreamEvent] = []
        self._states: list[AgentState] = []

    def record(self, event: StreamEvent, state: AgentState) -> None:
        """Append an event alongside a snapshot of the agent state."""

        self._events.append(event)
        self._states.append(state.snapshot())

    @property
    def events(self) -> tuple[StreamEvent, ...]:
        """Return the recorded events in emission order."""

        return tuple(self._events)

    @property
    def states(self) -> tuple[AgentState, ...]:
        """Return state snapshots for each recorded event."""

        return tuple(self._states)

    def __len__(self) -> int:
        return len(self._events)

    async def replay(self) -> AsyncIterator[StreamEvent]:
        """Yield recorded events as an async iterator."""

        for event in self._events:
            yield event


class AgentRuntime(AsyncIterator[StreamEvent]):
    """Coordinate adapter streaming, agent state, and transcript replay."""

    def __init__(
        self,
        adapter: ModelAdapter,
        messages: Sequence[Message],
        /,
        *,
        tools: Any | None = None,
        config: Mapping[str, Any] | None = None,
        transcript: SessionTranscript | None = None,
    ) -> None:
        self._adapter = adapter
        self._messages = tuple(messages)
        self._tools = tools
        self._config = dict(config or {})
        self._stream: BaseStreamIterator | None = None
        self._closed = False

        self.state = AgentState()
        self.transcript = transcript or SessionTranscript()

    def __aiter__(self) -> AgentRuntime:
        return self

    async def __anext__(self) -> StreamEvent:
        if self._closed:
            raise StopAsyncIteration

        iterator = self._ensure_stream()
        try:
            event = await iterator.__anext__()
        except StopAsyncIteration:
            await self.aclose()
            raise
        except CancelledError:
            await self.aclose()
            raise
        except Exception:
            await self.aclose()
            raise

        self._handle_event(event)

        if isinstance(event, FinalEvent):
            await self.aclose()

        return event

    @property
    def closed(self) -> bool:
        """Whether the runtime has been closed."""

        return self._closed

    async def aclose(self) -> None:
        """Close the underlying stream iterator and mark the runtime closed."""

        if self._closed:
            return

        self._closed = True
        iterator = self._stream
        self._stream = None
        if iterator is None:
            return

        closer = getattr(iterator, "aclose", None)
        if closer is not None:
            result = closer()
            if inspect.isawaitable(result):
                await result
            return

        await iterator.close()

    def on_event(self, event: TokenEvent) -> None:
        """Log token events emitted by the adapter."""

        LOGGER.debug("on_event index=%s content=%r", event.index, event.content)

    def on_tool(self, event: ToolCallEvent | ToolResultEvent) -> None:
        """Log tool call activity for observability."""

        if isinstance(event, ToolCallEvent):
            LOGGER.info(
                "on_tool call id=%s name=%s final=%s",
                event.id,
                event.name,
                event.is_final,
            )
        else:
            LOGGER.info("on_tool result id=%s", event.id)

    def on_complete(self, event: FinalEvent) -> None:
        """Log completion of the streaming session."""

        LOGGER.info(
            "on_complete output_length=%s tokens=%s",
            len(event.output),
            event.total_tokens,
        )

    def _ensure_stream(self) -> BaseStreamIterator:
        if self._stream is None:
            self._stream = self._adapter.stream(
                self._messages,
                tools=self._tools,
                **self._config,
            )
        return self._stream

    def _handle_event(self, event: StreamEvent) -> None:
        if isinstance(event, TokenEvent):
            self.state.tokens.append(event)
            self.state.memory.append(event.content)
            token_counts = self.state.metadata.setdefault("token_counts", 0)
            self.state.metadata["token_counts"] = token_counts + 1
            self.on_event(event)
        elif isinstance(event, ToolCallEvent):
            self._handle_tool_call(event)
        elif isinstance(event, ToolResultEvent):
            self._handle_tool_result(event)
        elif isinstance(event, FinalEvent):
            self._handle_final_event(event)
        else:  # pragma: no cover - defensive branch for future event types
            LOGGER.debug("Unhandled event type: %s", type(event).__name__)

        self.transcript.record(event, self.state)

    def _handle_tool_call(self, event: ToolCallEvent) -> None:
        tool_calls = self.state.metadata.setdefault("tool_calls", {})
        call_state = tool_calls.setdefault(
            event.id,
            {"name": event.name, "args": "", "is_final": False},
        )
        call_state["name"] = event.name
        call_state.setdefault("args", "")
        call_state["args"] += event.args_fragment
        call_state["is_final"] = event.is_final
        fragments = call_state.setdefault("fragments", [])
        fragments.append(event.args_fragment)

        self.state.last_tool = event if event.is_final else self.state.last_tool
        self.state.memory.append(f"tool_call:{event.name}")
        self.on_tool(event)

    def _handle_tool_result(self, event: ToolResultEvent) -> None:
        tool_results = self.state.metadata.setdefault("tool_results", {})
        tool_results[event.id] = event.output

        if self.state.last_tool and self.state.last_tool.id == event.id:
            self.state.last_tool = None

        self.state.memory.append(event.output)
        self.on_tool(event)

    def _handle_final_event(self, event: FinalEvent) -> None:
        self.state.metadata["final_output"] = event.output
        if event.total_tokens is not None:
            self.state.metadata["total_tokens"] = event.total_tokens

        self.state.memory.append(event.output)
        self.on_complete(event)
