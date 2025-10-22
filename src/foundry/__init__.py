"""Utilities for scaffolding new Python projects.

The package exposes helpers for converting human friendly project names into
module and class identifiers, renders small Jinja-less templates, and ships a
minimal project scaffolder that can be reused both programmatically and via the
command line interface.
"""

from __future__ import annotations

from .config import ProjectConfig
from .naming import normalize_class_name, normalize_module_name, slugify
from .scaffold import ProjectScaffolder
from .template import TemplateRenderer, TemplateRenderingError

__all__ = [
    "ProjectConfig",
    "ProjectScaffolder",
    "TemplateRenderer",
    "TemplateRenderingError",
    "normalize_class_name",
    "normalize_module_name",
    "slugify",
]

__version__ = "0.1.0"
