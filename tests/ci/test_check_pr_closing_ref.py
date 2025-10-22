import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.check_pr_closing_ref import (  # noqa: E402  (import after sys.path setup)
    check_pr_event,
    has_closing_reference,
    main,
)


@pytest.mark.parametrize(
    "body",
    [
        "Closes #123",
        "fixes #42",
        "Resolves #999",
        "Some text\n- closes #100",
        "Multiple references: Fixes #1 and resolves #2",
    ],
)
def test_has_closing_reference_valid(body: str) -> None:
    assert has_closing_reference(body)


@pytest.mark.parametrize(
    "body",
    [
        "",  # empty
        "This PR does something",
        "Closes 123",  # missing '#'
        "Closes#123",  # missing space before '#'
        "Closes #abc",  # non-numeric
    ],
)
def test_has_closing_reference_invalid(body: str) -> None:
    assert not has_closing_reference(body)


def test_check_pr_event_skips_with_label() -> None:
    event = {
        "pull_request": {
            "body": "",
            "labels": [{"name": "skip-pr-link-check"}],
        }
    }
    ok, message = check_pr_event(event)
    assert ok
    assert "skip" in message.lower()


@pytest.mark.parametrize(
    "body, expected_exit",
    [("Closes #1", 0), ("Missing reference", 1)],
)
def test_main_with_event_path(tmp_path: Path, capsys, body: str, expected_exit: int) -> None:
    event_path = tmp_path / "event.json"
    event = {
        "pull_request": {
            "body": body,
            "labels": [],
        }
    }
    event_path.write_text(json.dumps(event))

    exit_code = main(["--event-path", str(event_path)])
    captured = capsys.readouterr()
    assert exit_code == expected_exit
    assert captured.out.strip() != ""
    if expected_exit:
        assert "must include" in captured.out
    else:
        assert "Closing reference" in captured.out
