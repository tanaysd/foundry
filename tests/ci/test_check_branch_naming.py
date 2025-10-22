import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.check_branch_naming import (  # noqa: E402 (import after sys.path setup)
    ERROR_MESSAGE,
    check_branch,
    is_valid_branch_name,
    main,
)


@pytest.mark.parametrize(
    "branch",
    [
        "codex/tc-03-openai-adapter-scaffolding",
        "codex/tc-42-workflow-hardening",
        "codex/tc-123-ci-regression-fix",
        "codex/TC-42-workflow-hardening",
    ],
)
def test_is_valid_branch_name_accepts_compliant_branches(branch: str) -> None:
    assert is_valid_branch_name(branch)


@pytest.mark.parametrize(
    "branch",
    [
        "codex/run-codex-command",
        "codex-tc03",
        "codex/tc03/foo",
        "codex/tc-3-invalid",
        "codex/tc-123-title-with spaces",
    ],
)
def test_is_valid_branch_name_rejects_non_compliant_branches(branch: str) -> None:
    assert not is_valid_branch_name(branch)


@pytest.mark.parametrize(
    "branch, expected_ok, expected_message",
    [
        ("", False, "Branch name is not set. Provide --branch or GITHUB_REF_NAME."),
        (
            "codex/tc-03-openai-adapter-scaffolding",
            True,
            "Branch name `codex/tc-03-openai-adapter-scaffolding` matches the Codex convention.",
        ),
        ("codex/run-codex-command", False, ERROR_MESSAGE),
    ],
)
def test_check_branch_returns_expected_messages(
    branch: str, expected_ok: bool, expected_message: str
) -> None:
    ok, message = check_branch(branch)
    assert ok is expected_ok
    assert message == expected_message


def test_main_reads_branch_from_github_ref(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_REF_NAME", "codex/tc-42-workflow-hardening")
    exit_code = main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "workflow-hardening" in captured.out
    assert captured.err == ""


def test_main_reports_error_on_invalid_branch(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_REF_NAME", "codex/run-codex-command")
    exit_code = main([])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert ERROR_MESSAGE in captured.err


def test_main_falls_back_to_head_ref(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    monkeypatch.setenv("GITHUB_HEAD_REF", "codex/tc-03-openai-adapter-scaffolding")
    exit_code = main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "codex/tc-03-openai-adapter-scaffolding" in captured.out
