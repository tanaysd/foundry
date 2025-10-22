from __future__ import annotations

from pathlib import Path

import pytest

from foundry.config import ProjectConfig
from foundry.scaffold import ProjectScaffolder
from foundry.template import TemplateRenderer


@pytest.fixture()
def scaffolder() -> ProjectScaffolder:
    return ProjectScaffolder(TemplateRenderer())


def test_scaffolder_creates_expected_structure(tmp_path: Path, scaffolder: ProjectScaffolder):
    config = ProjectConfig.from_name("Sample App")
    project_dir = tmp_path / "project"
    scaffolder.create(config, project_dir)

    expected_files = [
        project_dir / "README.md",
        project_dir / "pyproject.toml",
        project_dir / "src" / config.package / "__init__.py",
        project_dir / "tests" / "__init__.py",
        project_dir / "tests" / "test_smoke.py",
    ]
    for path in expected_files:
        assert path.exists(), f"expected {path} to exist"


def test_scaffolder_respects_force(tmp_path: Path, scaffolder: ProjectScaffolder):
    config = ProjectConfig.from_name("Demo")
    project_dir = tmp_path / "project"
    scaffolder.create(config, project_dir)
    (project_dir / "README.md").write_text("custom", encoding="utf-8")

    with pytest.raises(FileExistsError):
        scaffolder.create(config, project_dir)

    scaffolder.create(config, project_dir, force=True)
    assert (project_dir / "README.md").read_text(encoding="utf-8").startswith("# Demo")
