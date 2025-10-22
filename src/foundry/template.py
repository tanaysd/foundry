"""Lightweight string templating utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping

from .naming import normalize_class_name, normalize_module_name, slugify

__all__ = [
    "TemplateRenderer",
    "TemplateRenderingError",
]


_PLACEHOLDER_PATTERN = re.compile(r"{{\s*(?P<expression>[^{}]+?)\s*}}")


class TemplateRenderingError(RuntimeError):
    """Raised when the renderer cannot evaluate a placeholder."""


def _resolve_value(context: Mapping[str, Any], dotted_path: str) -> Any:
    value: Any = context
    for segment in dotted_path.split("."):
        if isinstance(value, Mapping):
            if segment not in value:
                raise KeyError(segment)
            value = value[segment]
            continue
        if hasattr(value, segment):
            value = getattr(value, segment)
            if callable(value):
                value = value()
            continue
        raise KeyError(segment)
    return value


def _apply_filter(value: Any, filter_name: str, filters: Mapping[str, Callable[[Any], Any]]) -> Any:
    try:
        filter_func = filters[filter_name]
    except KeyError as exc:
        raise TemplateRenderingError(f"unknown filter '{filter_name}'") from exc

    return filter_func(value)


@dataclass(slots=True)
class TemplateRenderer:
    """Render templates with ``{{ placeholder|filters }}`` expressions."""

    filters: MutableMapping[str, Callable[[Any], Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.filters:
            self.filters.update(
                {
                    "upper": lambda value: str(value).upper(),
                    "lower": lambda value: str(value).lower(),
                    "title": lambda value: str(value).title(),
                    "slug": lambda value: slugify(value),
                    "module": lambda value: normalize_module_name(str(value)),
                    "class": lambda value: normalize_class_name(str(value)),
                    "repr": lambda value: repr(value),
                    "strip": lambda value: str(value).strip(),
                }
            )

    def render_string(
        self,
        template: str,
        context: Mapping[str, Any],
        *,
        missing: str = "keep",
    ) -> str:
        """Render ``template`` using ``context``.

        Parameters
        ----------
        template:
            The template string to evaluate.
        context:
            Mapping providing values for placeholders.
        missing:
            Controls what happens when a placeholder cannot be resolved. The
            supported policies are ``"keep"`` (return the placeholder unchanged),
            ``"empty"`` (replace with an empty string) and ``"error"`` (raise
            :class:`TemplateRenderingError`).
        """

        if missing not in {"keep", "empty", "error"}:
            raise ValueError("missing must be 'keep', 'empty', or 'error'")

        def substitute(match: re.Match[str]) -> str:
            expression = match.group("expression")
            parts = [part.strip() for part in expression.split("|") if part.strip()]
            if not parts:
                return match.group(0)

            key, *filters = parts
            try:
                value = _resolve_value(context, key)
            except KeyError:
                if missing == "keep":
                    return match.group(0)
                if missing == "empty":
                    return ""
                raise TemplateRenderingError(f"missing value for '{key}'")

            for filter_name in filters:
                value = _apply_filter(value, filter_name, self.filters)

            return str(value)

        return _PLACEHOLDER_PATTERN.sub(substitute, template)

    def render_file(
        self,
        template_path: str | Path,
        context: Mapping[str, Any],
        *,
        target: str | Path | None = None,
        encoding: str = "utf-8",
        missing: str = "keep",
    ) -> str:
        """Render ``template_path`` and optionally write the result to ``target``."""

        template_path = Path(template_path)
        if not template_path.is_file():
            raise FileNotFoundError(template_path)

        text = template_path.read_text(encoding=encoding)
        rendered = self.render_string(text, context, missing=missing)

        if target is not None:
            target_path = Path(target)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(rendered, encoding=encoding)

        return rendered

    def render_directory(
        self,
        template_dir: str | Path,
        target_dir: str | Path,
        context: Mapping[str, Any],
        *,
        missing: str = "keep",
        ignore: Iterable[str] | None = None,
    ) -> None:
        """Render every file inside ``template_dir`` into ``target_dir``."""

        template_dir = Path(template_dir)
        target_dir = Path(target_dir)
        if not template_dir.is_dir():
            raise FileNotFoundError(template_dir)

        ignore_patterns = set(ignore or [])
        for source in template_dir.rglob("*"):
            relative = source.relative_to(template_dir)
            if any(relative.match(pattern) for pattern in ignore_patterns):
                continue

            destination = target_dir / relative
            if source.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue

            self.render_file(source, context, target=destination, missing=missing)
