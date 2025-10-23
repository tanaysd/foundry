# Adapters

## OpenAI mapping (non-streaming)

Foundry's OpenAI adapter focuses on deterministic message translation and a
minimal `generate()` implementation that works with a fake client. The
implementation avoids network access and streaming support. Instead, it
concentrates on the following guarantees:

- **Strict schema:** Messages are represented by the `Message` model, which
  enforces one of three roles (`system`, `user`, `assistant`) and requires
  non-empty string content. The converters reject any additional provider
  fields to ensure JSON round-trips stay deterministic.
- **Pure converters:** `messages_to_openai()` transforms a sequence of Foundry
  messages into OpenAI's chat completion payload, while `openai_to_messages()`
  performs the inverse. Each helper validates roles and content and raises an
  `AdapterError` if data falls outside the supported schema.
- **Deterministic requests:** `OpenAIAdapter.generate()` injects
  `temperature=0` unless explicitly overridden, prevents caller supplied
  `messages`/`stream` overrides, and raises an error when streaming is
  requested.
- **Fake client friendly:** Tests construct a fake client exposing
  `chat.completions.create(**kwargs)`. The adapter returns the first assistant
  message from the response and surfaces malformed responses via `AdapterError`
  for deterministic failure handling.

These primitives establish a baseline for additional capabilities—such as tool
calling and streaming—to be layered on in future tasks while keeping core
behavior predictable and well tested.

## Function/Tool calling (non-streaming)

Tool support layers on top of the baseline adapter via the `ToolSpec` and
`ToolCall` primitives:

- **Declarative tool specs:** `ToolSpec` captures the canonical name,
  description, and JSON-schema parameters for a tool. Specifications are
  validated for JSON compatibility, required/optional coherence, and naming
  rules before being converted into provider payloads.
- **Provider mapping:** `tool_specs_to_openai()` maps `ToolSpec` instances to
  OpenAI's `type=function` schema, thawing the immutable parameter structure
  into JSON-serializable dictionaries. Duplicate tool names and malformed
  schemas raise `AdapterError` immediately.
- **Tool call normalization:** `normalize_tool_calls()` converts provider
  `tool_call` payloads into immutable `ToolCall` records. Arguments are parsed
  from JSON, validated for structure, and frozen to ensure deterministic
  comparisons across adapters.
- **Message conversions:** `messages_to_openai()`/`openai_to_messages()` now
  include tool call payloads. Assistant messages may carry empty textual
  content when tool invocations are present, and round-tripping preserves the
  normalized `ToolCall` tuples.
- **Adapter integration:** When `tools=[ToolSpec, ...]` is supplied to
  `OpenAIAdapter.generate()`, the adapter injects the mapped tool definitions
  into the request and normalizes the resulting tool calls into the returned
  assistant message. Invalid tool responses propagate as `AdapterError` for
  deterministic failure handling.

Together, these behaviors ensure the non-streaming tool pathway is type-safe,
deterministic, and backed by unit plus contract tests that keep Foundry and
provider semantics aligned.
