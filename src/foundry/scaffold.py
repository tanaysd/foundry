"""Project scaffolding helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import ProjectConfig
from .template import TemplateRenderer

__all__ = ["ProjectScaffolder"]


README_TEMPLATE = """# {{ name }}

{{ description|strip }}

## Development

- Create a virtual environment and install dependencies with `pip install -e .[dev]`.
- Run the test-suite with `pytest`.
"""

PYPROJECT_TEMPLATE = """[build-system]
requires = ["setuptools>=65.0"]
build-backend = "setuptools.build_meta"

[project]
name = "{{ slug }}"
version = "0.1.0"
description = "{{ description|strip }}"
readme = "README.md"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest"]

[tool.setuptools]
package-dir = {"" = "src"}
packages = ["{{ package_name }}"]
"""

INIT_TEMPLATE = (
    '"""Top level package for {{ name }}."""\n\n__all__ = ["__version__"]\n__version__ = "0.1.0"\n'
)

TEST_TEMPLATE = """from importlib import import_module


def test_package_importable():
    module = import_module("{{ package_name }}")
    assert hasattr(module, "__version__")
"""


@dataclass(slots=True)
class ProjectScaffolder:
    """Create a minimal Python project structure."""

    renderer: TemplateRenderer

    def __init__(self, renderer: TemplateRenderer | None = None) -> None:
        self.renderer = renderer or TemplateRenderer()

    def create(
        self,
        config: ProjectConfig,
        target_dir: str | Path,
        *,
        force: bool = False,
        extra_files: Iterable[tuple[str, str]] | None = None,
    ) -> Path:
        """Create a new project described by ``config`` inside ``target_dir``."""

        target_path = Path(target_dir).expanduser().resolve()
        target_path.mkdir(parents=True, exist_ok=True)

        context = dict(config.context())
        context.setdefault("package_name", config.package)
        context.setdefault("name", config.name)

        files: list[tuple[str, str]] = [
            ("README.md", README_TEMPLATE),
            ("pyproject.toml", PYPROJECT_TEMPLATE),
            (f"src/{config.package}/__init__.py", INIT_TEMPLATE),
            ("tests/__init__.py", ""),
            ("tests/test_smoke.py", TEST_TEMPLATE),
        ]

        if extra_files:
            files.extend(extra_files)

        for relative_path, template in files:
            destination = target_path / relative_path
            if destination.exists() and not force:
                raise FileExistsError(f"{destination} already exists")
            destination.parent.mkdir(parents=True, exist_ok=True)
            rendered = self.renderer.render_string(template, context)
            destination.write_text(rendered, encoding="utf-8")

        return target_path
