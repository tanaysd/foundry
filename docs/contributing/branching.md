# Branch Naming Convention

Consistent branch names make it possible to trace every change back to its Codex task card. The CI guard `scripts/ci/check_branch_naming.py` enforces the repository-wide pattern and blocks pushes or pull requests that drift from it.

## Pattern

```text
codex/tc-XX-description
```

- `codex/` — All automation branches start with the agent prefix.
- `tc-XX` — Link to the task card identifier. Use two or three digits (for example, `tc-03` or `tc-123`). The CI check is case-insensitive, so `TC-XX` also passes.
- `description` — A hyphenated slug summarizing the task. Only letters, numbers, and `-` are allowed; prefer lowercase for readability even though the guard is case-insensitive.

The corresponding regular expression is:

```regex
^codex/tc-[0-9]{2,3}-[a-z0-9-]+$
```

When compiled in Python the pattern uses `re.IGNORECASE` to tolerate uppercase segments such as `codex/TC-04-enforce-branch-naming`.

## Examples

| Status  | Branch name                               | Notes |
|---------|-------------------------------------------|-------|
| ✅ Valid | `codex/tc-03-openai-adapter-scaffolding`  | Two-digit task ID and lowercase slug. |
| ✅ Valid | `codex/tc-123-ci-regression-fix`          | Three-digit task ID for larger backlogs. |
| ✅ Valid | `codex/TC-04-enforce-branch-naming`       | Case-insensitive guard accepts uppercase `TC`. |
| ❌ Invalid | `codex/run-codex-command`                  | Missing task ID segment. |
| ❌ Invalid | `codex/tc03/foo`                           | Uses `/` instead of a hyphen between ID and slug. |
| ❌ Invalid | `codex/tc-3-invalid`                       | Task ID must use two or three digits. |
| ❌ Invalid | `codex/tc-123-title-with spaces`           | Spaces are not allowed; replace with hyphens. |

## Local Validation

The CI workflow `.github/workflows/check-branch-naming.yml` runs automatically on pushes and pull requests. To validate locally, run:

```bash
python scripts/ci/check_branch_naming.py --branch YOUR_BRANCH_NAME
```

The script exits with status code `0` when the name matches the pattern. Otherwise it prints:

```
Branch name must match codex/tc-XX-description pattern (e.g., codex/tc-03-openai-adapter).
```
