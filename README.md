# Foundry

[![CI Status](https://img.shields.io/badge/ci-passing-brightgreen.svg)](#) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](#)

> Local agent foundry — a toolkit for designing, building, and evaluating composable, testable AI agents.

Local agent foundry: design, build, and evaluate agentic systems.

Foundry is a modular, local-first framework for developing and evaluating agentic systems. It unifies schema definitions, adapters, evaluation harnesses, and observability tooling into a reproducible, test-driven workflow.

## Agent Operations Manual

See [AGENTS.md](./AGENTS.md) for Codex & AI contributor workflow.

## Features

- Type-safe schemas that define a shared contract between agents and tools.
- Model adapters for major providers including OpenAI, Anthropic, and Google.
- Evaluation harnesses and safety checks for validating reasoning traces.
- Observability, documentation, and iteration scaffolding for local-first development.

## Documentation

- [About Foundry](docs/about.md)

Perfect — here’s a clean, **GitHub-ready Foundry Roadmap Table**, summarizing everything from TC-01 through TC-10.
You can paste this directly into your `README.md` or a `ROADMAP.md` file — it’s designed to be both developer-legible and executive-readable.

---

## 🧭 Foundry Roadmap (TC-01 → TC-10)

| **Milestone** | **Capability / Focus Area**        | **Description**                                                                                         | **Key Artifacts**                                                                | **Status**                                   |
| ------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------- |
| **TC-01**     | 🧱 Repo Bootstrap                  | Initialize Foundry as an opinionated local agent lab. Set up structure, CLI, and baseline config.       | `pyproject.toml`, `foundry/__init__.py`                                          | ✅ Complete                                   |
| **TC-02**     | ⚙️ CI / Branch Governance          | Enforce branch-naming convention and GitHub Actions for CI quality gates.                               | `.github/workflows/check_branch_naming.yml`, `scripts/ci/check_branch_naming.py` | ✅ Complete                                   |
| **TC-03**     | 🤖 Codex Integration               | Enable Codex task-card workflow for automated implementation and testing.                               | `.github/issue_template.yaml`, `AGENTS.md`                                       | ✅ Complete                                   |
| **TC-04**     | 🧩 PR Review Brief                 | Generate PR review summaries with scope, risk, and API surface diffs.                                   | `scripts/ci/review_brief.py`, `review_template.md`                               | ⚙️ Partial (comment permissions fix pending) |
| **TC-05-A**   | 🧠 Streaming Core — Schema         | Define canonical event dataclasses and base async iterator for streaming outputs.                       | `stream.py` scaffold, `tests/test_stream_events.py`, `docs/adapters.md`          | ✅ Designed / Ready for Codex                 |
| **TC-05-B**   | 🧪 Streaming Core — Mock Client    | Implement deterministic mock iterator for local and CI testing (no live API).                           | `stream.py` extension, `test_openai_streaming_mock.py`                           | 🚧 Next in progress                          |
| **TC-05-C**   | 🔁 Streaming Core — Replay Helper  | Implement replay utility to reconstruct final outputs from event streams.                               | `stream.py`, `test_stream_replay.py`                                             | 🚧 Pending                                   |
| **TC-06**     | 🌐 OpenAI Adapter Integration      | Connect OpenAI SDK streaming responses to canonical `StreamEvent`s. Add normalization + error handling. | `openai.py`, `test_adapter_streaming.py`                                         | 🔜 Planned                                   |
| **TC-07**     | ⚡ Agent Runtime Loop               | Implement async event loop to consume streamed events, manage tools, memory, and reasoning.             | `runtime/loop.py`, `runtime/state.py`, `test_runtime_loop.py`                    | 🧩 Planned                                   |
| **TC-08**     | 📊 Evaluation Harness              | Build replay + scoring framework for agent sessions (deterministic eval).                               | `eval/metrics.py`, `test_eval_metrics.py`, `dashboards/`                         | 🔭 Planned                                   |
| **TC-09**     | 🪴 Vertical Agent: Gardening Coach | Develop first domain agent (gardening assistant) using Foundry stack.                                   | `/examples/gardensmith/`, `agent_recipe.yaml`                                    | 🌱 Planned                                   |
| **TC-10**     | 📱 Packaging & iOS Embedding       | Package as a Python/Swift hybrid module for mobile or local deployment.                                 | `/ios/FoundryKit/`, Swift bridge                                                 | 🧩 Future                                    |

---

### 📊 Progress Overview

| Phase                               | Focus                               | Progress      |
| ----------------------------------- | ----------------------------------- | ------------- |
| **Infrastructure**                  | Repo, CI, Codex, Governance         | ✅ 100%        |
| **Streaming Core (TC-05)**          | Event schema + mock stream + replay | ⚙️ ~60%       |
| **Adapter Layer (TC-06)**           | OpenAI + normalization              | ⏳ Not started |
| **Runtime + Evaluation (TC-07–08)** | Agent loop, observability, testing  | 🧩 In design  |
| **Vertical Recipes (TC-09–10)**     | Domain-specific agents, embedding   | 🔭 Upcoming   |

---

### 🧩 Architectural Trajectory

* **Phase 1** — *Infrastructure & Ops Foundation* (TC-01 → TC-04):
  Reproducible repo, governance, automation, and CI/Codex workflows.

* **Phase 2** — *Streaming & Adapters* (TC-05 → TC-06):
  Core abstraction for model outputs → normalized events → runtime-consumable format.

* **Phase 3** — *Runtime Intelligence* (TC-07 → TC-08):
  Event loop, memory, reasoning, and evaluation pipelines.

* **Phase 4** — *Vertical Agents* (TC-09 → TC-10):
  Specialized and generalized agents; local and mobile embeddings.

---

### 🧭 Summary

Foundry has progressed from a structured repo into a **codex-driven agent development environment**.
You now have:

* Deterministic CI + governance ✅
* Codex task automation ✅
* Streaming framework scaffold ✅
* Upcoming work: adapter integration → runtime → evaluation → agent recipes 🚀

---

## Installation

Foundry uses a `src/` layout. Install it in editable mode to begin experimenting:

```bash
pip install -e .[dev]
```

## Contributing

Contributions are welcome! Please open an issue to discuss significant changes before submitting a pull request.
