"""Guard to ensure PR bodies include a valid closing reference."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Iterable, Mapping, MutableMapping, Tuple, cast

CLOSING_PATTERN = re.compile(
    r"(?im)\b(close|closes|fix|fixes|resolve|resolves)\s+#\d+\b"
)
SKIP_LABEL = "skip-pr-link-check"


def has_closing_reference(body: str) -> bool:
    """Return True if the PR body contains an auto-closing reference."""
    if not body:
        return False
    return bool(CLOSING_PATTERN.search(body))


def has_skip_label(labels: Iterable[Mapping[str, object]]) -> bool:
    for label in labels or []:
        name = label.get("name") if isinstance(label, Mapping) else None
        if isinstance(name, str) and name.lower() == SKIP_LABEL:
            return True
    return False


def check_pr_event(event: Mapping[str, object]) -> Tuple[bool, str]:
    pr = event.get("pull_request") if isinstance(event, Mapping) else None
    if not isinstance(pr, Mapping):
        pr = {}

    labels = pr.get("labels") if isinstance(pr, Mapping) else None
    if not isinstance(labels, Iterable):
        labels = []

    if has_skip_label(labels):
        return True, "Skipping closing reference check due to `skip-pr-link-check` label."

    body = pr.get("body") if isinstance(pr, Mapping) else ""
    body_str = body if isinstance(body, str) else ""

    if has_closing_reference(body_str):
        return True, "Closing reference found in PR body."

    return (
        False,
        "PR body must include a closing keyword (e.g., `Closes #123`, `Fixes #123`, `Resolves #123`).",
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--event-path",
        default=None,
        help="Path to the GitHub event payload JSON file. Overrides $GITHUB_EVENT_PATH if provided.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def load_event(path: str) -> MutableMapping[str, object]:
    with open(path, "r", encoding="utf-8") as file:
        return cast(MutableMapping[str, object], json.load(file))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    event_path = args.event_path or os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("GITHUB_EVENT_PATH is not set and --event-path was not provided.", file=sys.stderr)
        return 1

    try:
        event = load_event(event_path)
    except FileNotFoundError:
        print(f"Event payload not found at: {event_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Failed to parse event payload JSON: {exc}", file=sys.stderr)
        return 1

    ok, message = check_pr_event(event)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
