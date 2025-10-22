# 🧠 AGENTS.md — Operating Manual for Codex and Other Automated Contributors

> _“Every agent is a teammate. Treat it like one: brief it, bound it, and review it.”_  
> — Foundry Design Principle #07

This document defines how intelligent agents (e.g., Codex, Claude Code, Gemini, etc.) interact with this repository.  
It ensures every autonomous contribution — code, documentation, or test — follows the same standards as human collaborators.  
Agents act as builders, not overlords: they write, test, document, and close their own work under human oversight.

---
## Purpose
Establish a unified operating protocol for AI agents contributing to this repository.  
All contributions must meet the same bar for review, testing, and traceability as human work.  
The goal: reproducibility, composability, and accountability across all agent-driven development.

---
## Philosophy
- **Deterministic > clever** — predictability and reproducibility first.  
- **Tests are contracts** — every behavior must be verifiable.  
- **Local first** — no hidden dependencies.  
- **Composable primitives** — agents should build reusable modules.  
- **Traceability** — every change links to a task card (`TC-###`) and its Issue.

---
## Task Intake Protocol
1. **Source of truth:**  
   Each task originates as a YAML task card in `.codex/tasks/` or as a GitHub Issue labeled `codex-task`.

2. **Required fields:**  
   `id`, `title`, `context`, `deliverables`, `test_plan`, `constraints`, `steps`, `acceptance_criteria`, `dependencies`, `auto_close`.

3. **Branch naming convention:**  
   ```
   codex/<task-id>-<slugified-title>
   # Example: codex/tc-003b-openai-generate-basic
   ```

4. **Pull Request policy:**  
   Every PR must include the line:
   ```
   Closes #<ISSUE_NUMBER>
   ```
   if `auto_close: true` is set in the task card.

5. **Commit format:**  
   ```
   [TC-XXX] <summary>
   ```
   Body: short rationale and relevant references.

---
## Code Generation Guidelines
**Language & Style**

- Python 3.11+, `src/` layout.  
- Type-safe (`mypy --strict`), linted (`ruff`), coverage ≥ 85%.  
- Prefer functional purity; use classes only when necessary.  
- No live API calls unless explicitly whitelisted.

**Testing Rules**

| Type | Path | Purpose |
|------|------|----------|
| Unit | `tests/<area>/` | Verify pure logic |
| Contract | `tests/contracts/` | Enforce cross-adapter invariants |
| Integration | `tests/integration/` | Validate composed flows |
| CI Safety | `tests/ci/` | Metadata, automation, and infra validation |

Tests must be deterministic and self-contained.  
Fixtures and mocks are preferred over live dependencies.

**Documentation**

- Each module must include a Markdown file under `docs/`.  
- Every component must describe its *Design Intent*.  
- Use Mermaid diagrams where helpful; keep output Markdown-only.

---
## Pull Request Lifecycle
| Phase | Action | Responsible |
|-------|---------|-------------|
| Intake | Parse linked Issue / task card | Codex |
| Implementation | Generate code, tests, and docs | Codex |
| Verification | Run `make lint`, `make type`, `make test` | Codex |
| PR Creation | Draft PR referencing Issue | Codex |
| Review | Validate, test, and discuss | Maintainer |
| Merge | “Squash & Merge” to `main` | Maintainer / Codex |
| Close | GitHub auto-closes via `Closes #<issue>` | GitHub |

**Rule:** No PR merges until all acceptance criteria in the task card are satisfied.

---
## Safety & Guardrails
Agents **must never**:

- Push directly to `main`.  
- Execute or import unverified code.  
- Remove existing tests without replacement.  
- Commit secrets or credentials.

**Guardrail scripts:**

- `scripts/ci/check_pr_closing_ref.py` — ensures PRs link to Issues.  
- `scripts/ci/enforce_tests_exist.py` — ensures all deliverables are tested.  
- `scripts/ci/check_metadata_sync.py` — ensures `README` and `pyproject.toml` are aligned.

---
## Communication Protocol
Agents may post structured GitHub comments:

```
### 🧩 Codex Update
Task: TC-003B — OpenAI adapter non-streaming generate()
Phase: Planning → Implementation → Review
Notes:
- Created branch codex/tc-003b-openai-generate-basic
- Generated deliverables:
  - src/foundry/core/adapters/openai.py
  - tests/adapters/test_openai_generate_basic.py
Next: Running tests locally.
```

Humans may reply with operational directives:

```
@codex please re-run with stricter mypy config
```

---
## Evaluation Loop
Each agent run is evaluated on:

| Metric | Description |
|---------|--------------|
| **Correctness** | Tests pass successfully |
| **Style Adherence** | Linting, typing, documentation |
| **Autonomy** | % of tasks completed without intervention |
| **Reusability** | Composability of outputs |
| **Safety** | No policy or security violations |

All results are logged in `reports/agent_runs.json`.

---
## Extending the Foundry Agent Ecosystem
Agents integrated with this repository must register in `agents/registry.yaml`:

```yaml
- id: codex
  role: builder
  capabilities: [codegen, tests, docs, pr-automation]
  entrypoint: .codex/
- id: claude
  role: reviewer
  capabilities: [code-review, test-summarization]
- id: gemini
  role: researcher
  capabilities: [docs-refinement, experiment-tracking]
```

Agents must describe their roles and capabilities when updating the registry.

---
## Golden Rules
1. Every change maps to a task card.  
2. Every deliverable has a test.  
3. Every PR auto-closes its Issue.  
4. Every merge leaves `main` buildable and type-checked.  

---
## Quick Reference
| Command | Purpose |
|----------|----------|
| `make setup` | Initialize environment |
| `make lint` | Run linter |
| `make type` | Run strict type checks |
| `make test` | Execute tests |
| `make docs` | Serve documentation |
| `make ci` | Full local CI pipeline |
| `make report` | Summarize agent metrics |

---
## License
All agent contributions are governed by the repository’s license (Apache-2.0).  
Submitting contributions implies agreement to the Contributor License Agreement in `CONTRIBUTING.md`.

---
### Closing Note
> **Foundry** is not just a toolkit *for* agents — it’s a foundry *run by* agents.  
> Treat this file as your operational contract: every improvement, by Codex or by humans, strengthens the system.
