# Foundry I/O Layer

The Foundry I/O layer defines the common data contracts and runtime interfaces that
agents, planners, and evaluators use to exchange information. It is intentionally
minimal and file-system friendly so that new adapters can be prototyped without
infrastructure dependencies.

## Schemas

The schemas live in [`foundry/io/schema.py`](../src/foundry/io/schema.py) and are
implemented with **Pydantic v2** models configured for strict validation:

- `AgentInput` – immutable representation of messages delivered to an agent.
- `AgentOutput` – responses emitted by an agent, optionally linked back to the
  originating input via `in_reply_to`.
- `SystemEvent` – structured telemetry and diagnostics, tagged with an
  `EventLevel` severity and arbitrary JSON metadata.
- `ExecutionTrace` – aggregation of inputs, outputs, and events that describe a
  single agent run.

All models forbid unknown fields and only accept JSON-compatible payloads. They
round-trip cleanly through `model_dump(mode="json")` and
`model_validate_json(...)`, making persistence and transport straightforward.

## Interfaces

[`foundry/io/interfaces.py`](../src/foundry/io/interfaces.py) declares the
abstract base classes that adapters must implement:

- `InputChannel` exposes `read()` to retrieve the next `AgentInput` and
  `flush()` to clear buffered state.
- `OutputChannel` provides `write()` for persisting an `AgentOutput` and
  `flush()` to ensure durability.
- `EventBus` mirrors the same contract for `SystemEvent` telemetry.

The interfaces are intentionally small so that adapters can wrap message queues,
HTTP APIs, or any other transport with minimal ceremony.

## Local adapter

For testing and local development there is a filesystem-backed adapter in
[`foundry/io/adapters/local.py`](../src/foundry/io/adapters/local.py). It stores
inputs, outputs, and events as JSON files under a base directory and removes
messages once they are read. The helper `LocalIO` class wires together the input,
output, and event components while exposing convenience methods for injecting
messages during tests.

### Extending the adapter set

New adapters should implement the three abstract interfaces and adhere to the
same JSON payload contracts used by the schemas. The minimal `read()`, `write()`,
and `flush()` API makes it easy to map onto streaming systems (Pub/Sub, Kafka),
object stores (S3), or RPC endpoints. When building a new adapter:

1. Reuse the Pydantic models for serialization to guarantee compatibility.
2. Validate messages immediately upon ingress to fail fast on schema drift.
3. Keep `flush()` lightweight—ideally delegating to the underlying transport’s
   native durability guarantees.
4. Add tests that perform roundtrip serialization using the shared models.

By following these guidelines, all components of Foundry can interoperate across
local, staging, and production environments without diverging schemas.
