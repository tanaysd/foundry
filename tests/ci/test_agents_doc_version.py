"""Ensure AGENTS.md stays in sync across documentation surfaces."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
DOCS_AGENTS_PATH = REPO_ROOT / "docs" / "agents.md"

EXPECTED_SHA256 = "2bc75358e32d7142a41e6f2e61ee467f69a871a3f6a408621a3db5153cc59226"
REQUIRED_HEADINGS = [
    "# 🧠 AGENTS.md — Operating Manual for Codex and Other Automated Contributors",
    "## Purpose",
    "## Philosophy",
    "## Task Intake Protocol",
    "## Code Generation Guidelines",
    "## Pull Request Lifecycle",
    "## Safety & Guardrails",
    "## Communication Protocol",
    "## Evaluation Loop",
    "## Extending the Foundry Agent Ecosystem",
    "## Golden Rules",
    "## Quick Reference",
    "## License",
    "### Closing Note",
]


@pytest.fixture()
def agents_manual() -> str:
    if not AGENTS_PATH.is_file():
        pytest.fail(f"Missing root manual at {AGENTS_PATH}")
    return AGENTS_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def docs_manual() -> str:
    if not DOCS_AGENTS_PATH.is_file():
        pytest.fail(f"Missing docs manual at {DOCS_AGENTS_PATH}")
    return DOCS_AGENTS_PATH.read_text(encoding="utf-8")


def test_agents_manual_hash_matches_approved_version(agents_manual: str) -> None:
    digest = hashlib.sha256(agents_manual.encode("utf-8")).hexdigest()
    assert digest == EXPECTED_SHA256


def test_docs_manual_matches_root_manual(agents_manual: str, docs_manual: str) -> None:
    assert docs_manual == agents_manual


@pytest.mark.parametrize("heading", REQUIRED_HEADINGS)
def test_manual_contains_required_headings(agents_manual: str, heading: str) -> None:
    assert heading in agents_manual
