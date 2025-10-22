# Contributing

## Auto-closing Issues via PRs

Pull requests created from task cards should automatically close their source issues when merged. To support this flow:

- Every new PR starts from the template in `.github/pull_request_template.md`. It includes a `Closes #` placeholder under **Related Task Card**.
- When a task card sets `auto_close: true`, Codex replaces the placeholder with the originating issue number (for example, `Closes #123`). Humans following the template should do the same when preparing PRs manually.
- The CI workflow `.github/workflows/check-pr-links.yml` validates that the PR body contains a closing keyword (`Closes`, `Fixes`, or `Resolves`) paired with an issue number.
- If a PR legitimately should not close an issue—such as repository-wide maintenance—you can apply the `skip-pr-link-check` label to bypass the guard.

To keep CI passing:

1. Leave the `Closes #` line in place and fill in the correct issue number before opening or updating the PR.
2. Use one of the supported keywords (case-insensitive): `Closes`, `Fixes`, or `Resolves`.
3. Ensure the issue reference includes the `#` symbol and a numeric identifier (for example, `Fixes #42`).
4. Only remove the line when the PR carries the `skip-pr-link-check` label.

Merging a PR with a valid closing reference automatically closes the referenced issue once the merge completes.
