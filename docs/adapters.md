# Adapters

## OpenAI mapping (non-streaming, no tools)

Foundry's OpenAI adapter focuses on deterministic message translation and a
minimal `generate()` implementation that works with a fake client. The
implementation avoids network access and omits tool calling or streaming
support. Instead, it concentrates on the following guarantees:

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
  `messages`/`stream` overrides, and raises an error when tools or streaming are
  requested.
- **Fake client friendly:** Tests construct a fake client exposing
  `chat.completions.create(**kwargs)`. The adapter returns the first assistant
  message from the response and surfaces malformed responses via `AdapterError`
  for deterministic failure handling.

These primitives establish a baseline for additional capabilities—such as tool
calling and streaming—to be layered on in future tasks while keeping core
behavior predictable and well tested.
