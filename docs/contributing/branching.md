# Branch Naming Convention

Consistent branch names make it possible to trace every change back to its Codex task card. The CI guard `scripts/ci/check_branch_naming.py` enforces the repository-wide pattern and blocks pushes or pull requests that drift from it.

## Pattern

```text
codex/tc-XX-description
```

- `codex/` — All automation branches start with the agent prefix.
- `tc-XX` — Link to the task card identifier. Use two or three digits (for example, `tc-03` or `tc-123`).
- `description` — A lowercase, hyphenated slug summarizing the task. Only `a-z`, `0-9`, and `-` are allowed.

The corresponding regular expression is:

```regex
^codex/tc-[0-9]{2,3}-[a-z0-9-]+$
```

## Examples

| Status  | Branch name                               | Notes |
|---------|-------------------------------------------|-------|
| ✅ Valid | `codex/tc-03-openai-adapter-scaffolding`  | Two-digit task ID and lowercase slug. |
| ✅ Valid | `codex/tc-123-ci-regression-fix`          | Three-digit task ID for larger backlogs. |
| ❌ Invalid | `codex/run-codex-command`                  | Missing task ID segment. |
| ❌ Invalid | `codex/tc03/foo`                           | Uses `/` instead of a hyphen between ID and slug. |
| ❌ Invalid | `codex/tc-3-Uppercase`                     | Task ID is a single digit and slug contains uppercase characters. |

## Local Validation

The CI workflow `.github/workflows/check-branch-naming.yml` runs automatically on pushes and pull requests. To validate locally, run:

```bash
python scripts/ci/check_branch_naming.py --branch YOUR_BRANCH_NAME
```

The script exits with status code `0` when the name matches the pattern. Otherwise it prints:

```
Branch name must match codex/tc-XX-description pattern (e.g., codex/tc-03-openai-adapter).
```
