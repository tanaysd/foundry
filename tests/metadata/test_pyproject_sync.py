from __future__ import annotations

from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
ABOUT_PATH = REPO_ROOT / "docs" / "about.md"

SHORT_DESCRIPTION = (
    "Local agent foundry — a toolkit for designing, building, and evaluating composable, "
    "testable AI agents."
)
MEDIUM_DESCRIPTION = (
    "Foundry is a modular, local-first framework for developing and evaluating agentic systems. "
    "It unifies schema definitions, adapters, evaluation harnesses, and observability tooling "
    "into a reproducible, test-driven workflow."
)
LONG_DESCRIPTION = (
    "Foundry provides the building blocks for high-assurance agent development: schemas that "
    "define the lingua franca between agents; adapters that connect to major model providers "
    "(OpenAI, Anthropic, Google); a safety and evaluation layer for validating reasoning "
    "traces; and a documentation scaffold for iterative experimentation. Every component is "
    "type-safe, testable, and built for composability. Foundry is the foundation for creating "
    "vertical and general purpose agents in a local, reproducible environment."
)


def load_pyproject() -> dict:
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)


def test_readme_and_pyproject_descriptions_are_in_sync() -> None:
    pyproject = load_pyproject()
    description = pyproject["project"]["description"]
    readme_text = README_PATH.read_text(encoding="utf-8")

    assert description in readme_text, "README must include the project description from pyproject.toml"


def test_readme_contains_expected_identity_copy() -> None:
    readme_text = README_PATH.read_text(encoding="utf-8")

    assert SHORT_DESCRIPTION in readme_text
    assert MEDIUM_DESCRIPTION in readme_text


def test_docs_about_contains_long_description() -> None:
    about_text = ABOUT_PATH.read_text(encoding="utf-8")

    assert LONG_DESCRIPTION in about_text
