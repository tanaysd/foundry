# Adapter Layer

Foundry's adapter layer translates provider-specific streaming payloads into a
canonical sequence of events. Downstream components consume **only** the
canonical dataclasses, which keeps the runtime provider-agnostic and enables
deterministic replay.

## Canonical Streaming Contract

Every adapter implements the [`BaseAdapter`](../src/foundry/adapters/base.py)
protocol:

```python
from collections.abc import AsyncIterator
from typing import Any

from foundry.adapters import BaseAdapter, BaseEvent


class ProviderAdapter(BaseAdapter):
    def stream(self, prompt: str, /, **kwargs: Any) -> AsyncIterator[BaseEvent]:
        ...
```

Calling `stream()` returns an async iterator that yields canonical events with
deterministic metadata:

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
- `FinalEvent(seq_id, ts, output, finish_reason, usage)` — terminal event.
  Exactly one final event is produced per stream.

Provider payloads never escape the adapter boundary; everything is projected
into these dataclasses.

### Determinism Guarantees

Adapters use deterministic helpers to keep ordering stable:

- `monotonic_seq()` yields strictly increasing integers. Each stream receives a
  fresh counter, guaranteeing reproducible `seq_id` ordering.
- `stable_ts()` returns timestamps relative to a fixed origin (`2024-01-01Z`)
  in one millisecond increments. The helper is side-effect free, enabling
  repeatable tests.

The utilities live in `foundry.adapters.openai_adapter` and can be copied or
reused by future providers.

### Error Policy

Any provider failure or malformed payload must be wrapped in
`AdapterStreamError`. This ensures a consistent surface for the runtime and for
tests. Adapter implementations should validate all external inputs, including
tool schemas, streaming chunks, and user-supplied kwargs, before converting
them into canonical events.

### Test Policy

Adapters ship with deterministic, offline tests that rely on fakes or fixtures
rather than live network calls. The OpenAI adapter's parity suite demonstrates
the pattern:

| Scenario | Covered By | Notes |
| --- | --- | --- |
| Token-only response | `tests/test_openai_adapter_parity.py::test_token_only_stream_matches_expected_sequence` | Verifies event ordering, timestamps, and usage metadata. |
| Tool call flow | `tests/test_openai_adapter_parity.py::test_tool_call_flow_emits_canonical_events` | Confirms argument merging, tool results, and final parity. |
| Interface contract | `tests/test_openai_adapter_contract.py` | Ensures the adapter satisfies the `BaseAdapter` protocol. |
| Edge cases | `tests/test_openai_adapter_edges.py` | Covers cancellation, empty outputs, and error propagation. |

All scenarios run offline via `pytest` and do not contact OpenAI.

## OpenAI Streaming Adapter

`OpenAIAdapter` wires the OpenAI Chat Completions streaming API into the
canonical contract. Highlights:

- **Payload construction:** prompts become the minimal message payload and are
  merged with deterministic defaults (`temperature=0`). Tool definitions accept
  either `ToolSpec` instances or raw provider dictionaries.
- **Chunk normalization:** every provider chunk is validated and converted into
  canonical events. Tool calls accumulate argument fragments, merge them when
  `finish_reason == "tool_calls"`, and emit a single `ToolCallEvent` per
  invocation. Tool results and token deltas retain causal ordering.
- **Finalization:** final events record the finish reason and optional token
  usage (`{"total_tokens": ...}`). Streams close automatically as soon as the
  `FinalEvent` is emitted or consumers call `aclose()`.
- **Error isolation:** malformed payloads and provider failures are wrapped in
  `AdapterStreamError`, ensuring a consistent error surface.

## Provider Integration Checklist

Use this checklist when adding a new adapter. It mirrors the CI gate enforced
for providers:

- [ ] Adapter class lives in `foundry/adapters/<provider>_adapter.py` and is
      exported from `foundry/adapters/__init__.py`.
- [ ] `stream()` validates inputs, calls the provider, and yields canonical
      events with deterministic `seq_id`/`ts` values.
- [ ] Tool call deltas are buffered until completion and parsed into structured
      JSON arguments.
- [ ] All provider errors are wrapped in `AdapterStreamError` and surfaced with
      actionable messages.
- [ ] Offline fakes or fixtures back the test suite—no live API calls.
- [ ] Parity tests exercise token-only, tool-call, and error scenarios via the
      shared adapter harness.
- [ ] Documentation in this file explains any provider-specific chunk shape or
      metadata.
- [ ] `make lint`, `make type`, and `make test` pass locally.

Keeping adapters deterministic and offline-testable ensures Foundry's runtime
can swap providers, replay sessions, and evaluate behaviors without side
effects.
