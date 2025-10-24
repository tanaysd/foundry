# Adapter Layer

Foundry's adapter layer translates provider-specific streaming payloads into a
canonical sequence of events that downstream components can consume without
knowing which SDK produced them. The OpenAI adapter is the first concrete
implementation and acts as the template for future providers.

## Canonical Streaming Contract

Adapters implement the `BaseAdapter` protocol:

```python
from collections.abc import AsyncIterator
from foundry.adapters import BaseAdapter, BaseEvent

class ProviderAdapter(BaseAdapter):
    def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[BaseEvent]:
        ...
```

Calling `stream()` returns an async iterator that yields only canonical events.
Each event carries deterministic metadata:

| Field | Description |
| --- | --- |
| `seq_id` | Strictly monotonic sequence counter starting at `0`. |
| `ts` | Deterministic timestamp derived from a stable clock origin. |

Four concrete dataclasses model streaming activity:

- `TokenEvent(seq_id, ts, content, index)` — incremental assistant tokens.
- `ToolCallEvent(seq_id, ts, call_id, name, args)` — normalized tool
  invocations. All argument fragments are merged and parsed into a single JSON
  object.
- `ToolResultEvent(seq_id, ts, call_id, output)` — tool outputs emitted after a
  `ToolCallEvent`.
- `FinalEvent(seq_id, ts, output, finish_reason, usage)` — terminal event. Exactly
  one final event is produced per stream.

No provider-specific payloads escape the adapter boundary; downstream code only
sees these dataclasses.

## Deterministic Sequencing

Two small utilities keep ordering and timestamps stable:

- `monotonic_seq()` yields strictly increasing integers. Every stream receives a
  fresh counter, guaranteeing deterministic replay.
- `stable_ts()` returns timestamps relative to a fixed origin (`2024-01-01Z`) in
  one millisecond increments. The function is side-effect free, enabling
  repeatable tests.

Both helpers live in `foundry.adapters.openai_adapter` and can be reused by
future providers.

## OpenAI Streaming Adapter

`OpenAIAdapter` wires the OpenAI Chat Completions streaming API into the
canonical contract. Highlights:

- **Payload construction:** prompts are turned into the minimal OpenAI message
  payload and merged with deterministic defaults (`temperature=0`). Tool
  definitions accept either `ToolSpec` instances or raw provider dictionaries.
- **Chunk normalization:** every provider chunk is validated and converted into
  canonical events. Tool calls accumulate argument fragments, merge them when
  `finish_reason == "tool_calls"`, and surface a single `ToolCallEvent` per
  invocation. Tool results and token deltas retain causal ordering.
- **Finalization:** final events record the finish reason and optional token
  usage (`{"total_tokens": ...}`). Streams close automatically as soon as the
  `FinalEvent` is emitted or consumers call `aclose()`.
- **Error isolation:** malformed payloads and provider failures are wrapped in
  `AdapterStreamError`, ensuring a consistent error surface.

### Test Matrix

The OpenAI adapter ships with deterministic, offline tests backed by a fake
client (`tests/fixtures/openai_fake.py`):

| Scenario | Covered By | Notes |
| --- | --- | --- |
| Token-only response | `tests/test_openai_adapter_parity.py::test_token_only_stream_matches_expected_sequence` | Verifies event ordering, timestamps, and usage metadata. |
| Tool call flow | `tests/test_openai_adapter_parity.py::test_tool_call_flow_emits_canonical_events` | Confirms argument merging, tool results, and final parity. |
| Interface contract | `tests/test_openai_adapter_contract.py` | Ensures the adapter satisfies the `BaseAdapter` protocol. |
| Edge cases | `tests/test_openai_adapter_edges.py` | Covers cancellation, empty outputs, and error propagation. |

All tests run offline via `pytest` and do not contact OpenAI.

## Adding a Provider Adapter

To add a new provider, follow this checklist:

1. **Create the adapter class** under `foundry/adapters/<provider>_adapter.py`.
   Implement the `BaseAdapter` protocol and expose the class from
   `foundry/adapters/__init__.py`.
2. **Translate provider chunks** into canonical events. Reuse `monotonic_seq()`
   and `stable_ts()` (or equivalents) to keep `seq_id` and `ts` deterministic.
3. **Normalize tool calls** by buffering argument fragments until the provider
   marks the call complete. Parse arguments into JSON objects before emitting a
   `ToolCallEvent`.
4. **Emit a single `FinalEvent`**. Capture finish reasons and any usage metrics
   needed for observability.
5. **Write offline tests** mirroring the scenarios in `tests/test_openai_adapter_*.py`.
   Provide fake streams or fixtures so CI can run without network access.
6. **Document provider specifics** in this file, focusing on any differences in
   chunk structure or additional canonical metadata.

A skeleton test module might look like:

```python
from foundry.adapters import BaseEvent
from foundry.adapters.myprovider_adapter import MyProviderAdapter

async def test_myprovider_token_stream(fake_client):
    adapter = MyProviderAdapter(fake_client, default_model="model")
    stream = adapter.stream("Prompt")
    events: list[BaseEvent] = [event async for event in stream]
    ...
```

Keeping adapters deterministic and offline-testable ensures Foundry's runtime can
swap providers, replay sessions, and evaluate behaviors without side effects.
