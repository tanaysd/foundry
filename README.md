# Foundry

[![CI Status](https://img.shields.io/badge/ci-passing-brightgreen.svg)](#) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](#)

> Local agent foundry — a toolkit for designing, building, and evaluating composable, testable AI agents.

Local agent foundry: design, build, and evaluate agentic systems.

Foundry is a modular, local-first framework for developing and evaluating agentic systems. It unifies schema definitions, adapters, evaluation harnesses, and observability tooling into a reproducible, test-driven workflow.

## Features

- Type-safe schemas that define a shared contract between agents and tools.
- Model adapters for major providers including OpenAI, Anthropic, and Google.
- Evaluation harnesses and safety checks for validating reasoning traces.
- Observability, documentation, and iteration scaffolding for local-first development.

## Documentation

- [About Foundry](docs/about.md)

## Installation

Foundry uses a `src/` layout. Install it in editable mode to begin experimenting:

```bash
pip install -e .[dev]
```

## Contributing

Contributions are welcome! Please open an issue to discuss significant changes before submitting a pull request.
