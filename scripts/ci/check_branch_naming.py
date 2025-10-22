"""Validate branch naming convention for Codex-driven tasks."""
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Iterable, Mapping

BRANCH_PATTERN = re.compile(r"^codex/tc-[0-9]{2,3}-[a-z0-9-]+$", re.IGNORECASE)
ERROR_MESSAGE = (
    "Branch name must match codex/tc-XX-description pattern (e.g., codex/tc-03-openai-adapter)."
)


def is_valid_branch_name(branch: str) -> bool:
    """Return True when *branch* complies with the enforced naming convention."""
    if not isinstance(branch, str):
        return False
    return bool(BRANCH_PATTERN.fullmatch(branch.strip()))


def check_branch(branch: str) -> tuple[bool, str]:
    """Validate *branch* and return a tuple of success flag and message."""
    cleaned = branch.strip() if isinstance(branch, str) else ""
    if not cleaned:
        return False, "Branch name is not set. Provide --branch or GITHUB_REF_NAME."

    if is_valid_branch_name(cleaned):
        return True, f"Branch name `{cleaned}` matches the Codex convention."

    return False, ERROR_MESSAGE


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--branch",
        default=None,
        help="Override the branch name to validate (defaults to $GITHUB_REF_NAME).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def determine_branch(env: Mapping[str, str], override: str | None) -> str:
    if override:
        return override
    return env.get("GITHUB_REF_NAME") or env.get("GITHUB_HEAD_REF") or ""


def main(argv: Iterable[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = parse_args(argv)
    environment: Mapping[str, str] = env if env is not None else os.environ
    branch = determine_branch(environment, args.branch)

    ok, message = check_branch(branch)
    output = sys.stdout if ok else sys.stderr
    print(message, file=output)
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
