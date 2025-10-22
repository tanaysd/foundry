"""Configuration helpers shared by the project scaffolder and CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .naming import normalize_class_name, normalize_module_name, slugify


@dataclass(slots=True)
class ProjectConfig:
    """Derived identifiers describing a new project.

    Attributes
    ----------
    name:
        The display name for the project provided by the user. This value is
        preserved verbatim and is primarily used for documentation.
    slug:
        A URL and filesystem friendly version of :attr:`name`.
    package:
        The sanitized Python package name that will be used for the ``src``
        directory.
    class_name:
        A canonical class name derived from :attr:`name`. Useful for generating
        boilerplate code such as an application entry point.
    description:
        A short, optional sentence describing the project. When no description
        is provided the :class:`ProjectConfig` will fall back to a sensible
        placeholder so templates always have something meaningful to render.
    """

    name: str
    slug: str
    package: str
    class_name: str
    description: str = ""

    @classmethod
    def from_name(
        cls,
        name: str,
        *,
        package: str | None = None,
        class_name: str | None = None,
        description: str = "",
    ) -> "ProjectConfig":
        """Build a :class:`ProjectConfig` from a human friendly project name.

        Parameters
        ----------
        name:
            The descriptive name chosen by the caller.
        package:
            Optionally override the automatically generated package name.
        class_name:
            Optionally override the generated class name.
        description:
            An optional short summary of the project.
        """

        normalized_name = " ".join(name.split())
        if not normalized_name:
            raise ValueError("project name must not be empty")

        slug = slugify(normalized_name)
        package_name = package or normalize_module_name(normalized_name)
        class_identifier = class_name or normalize_class_name(normalized_name)
        summary = description.strip()

        if not summary:
            summary = "TODO: Describe your project."

        return cls(
            name=normalized_name,
            slug=slug,
            package=package_name,
            class_name=class_identifier,
            description=summary,
        )

    def context(self) -> Mapping[str, str]:
        """Return a dictionary compatible with the templating helpers."""

        return {
            "name": self.name,
            "slug": self.slug,
            "package_name": self.package,
            "class_name": self.class_name,
            "description": self.description,
        }
