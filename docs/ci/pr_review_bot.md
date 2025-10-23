# PR Review Brief Bot

The PR Review Brief bot summarizes every pull request so reviewers can focus on high-signal insights instead of scrolling through large diffs. The automation is implemented entirely within this repository and runs on every `pull_request` event.

## How it works

1. The workflow in `.github/workflows/pr-review-brief.yml` checks out the pull request head SHA.
2. Python 3.11 is installed together with the project dependencies, `pytest`, and `pytest-cov`.
3. Tests run with coverage enabled. Failures do not break the workflow in this card—the bot is warn-only.
4. `scripts/ci/review_brief.py` computes:
   - the task card ID and linked issue from the PR metadata,
   - changed file scope and risk level,
   - coverage deltas for touched modules,
   - public API changes in `src/` via `scripts/ci/diff_api_surface.py`,
   - touched contract tests.
5. `peter-evans/create-or-update-comment@v4` posts or updates a comment containing the rendered brief.

The resulting comment is deterministic Markdown with sections for Task, Risk, Scope, Coverage, API Changes, Contracts, and Notes.

## Coverage behaviour

- Coverage data comes from `coverage.xml` created by the pytest invocation.
- If the baseline branch also has a `coverage.xml`, deltas per file are reported.
- The soft coverage gate (`scripts/ci/coverage_gate.py`) surfaces files that fall below 85 percent line coverage. The gate never fails the job; it only emits warnings.

## API surface diffing

`diff_api_surface.py` parses both the base and head versions of the `src/` tree and captures public classes, methods, and functions. Additions, removals, and signature changes are grouped separately so reviewers can quickly inspect user-facing changes.

## Contracts

Any file under `tests/contracts/` that appears in the diff is listed explicitly. When a pull request touches high-risk runtime code but no contracts, the brief reminds the author to run the contract suite manually.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Comment missing | Workflow did not run (check PR events) | Trigger a new push or rerun the workflow |
| Coverage section empty | `coverage.xml` missing or malformed | Ensure pytest produced a report and rerun |
| API changes missing expected entries | Code lives outside `src/` | Update the package layout or extend the bot if needed |

For deeper instrumentation, run the scripts locally:

```bash
pytest -q --maxfail=1 --disable-warnings --cov=src --cov-report=xml
python scripts/ci/review_brief.py --base <base-sha> --head HEAD --pr <number> --repo <owner/name>
```
