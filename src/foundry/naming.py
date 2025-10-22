"""String normalisation utilities used throughout the project."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

__all__ = ["slugify", "normalize_module_name", "normalize_class_name"]


_SEPARATORS = re.compile(r"[\s\-]+")
_INVALID_IDENTIFIER = re.compile(r"[^0-9a-zA-Z_]")
_MULTIPLE_UNDERSCORES = re.compile(r"_+")


def _collapse_whitespace(value: str) -> str:
    return _SEPARATORS.sub(" ", value).strip()


def slugify(value: str | Iterable[str], *, separator: str = "-", allow_unicode: bool = False) -> str:
    """Create a filesystem and URL friendly slug from ``value``.

    Parameters
    ----------
    value:
        The text to normalise. When an iterable of strings is provided the values
        are joined with spaces before slugification.
    separator:
        The character used to join individual words. ``separator`` must consist
        of a single visible ASCII character.
    allow_unicode:
        When ``True`` unicode characters are preserved. Otherwise the result is
        restricted to ASCII.
    """

    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        value = " ".join(str(part) for part in value)

    text = str(value)
    if not allow_unicode:
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
    else:
        text = unicodedata.normalize("NFKC", text)

    text = re.sub(r"[\s]+", " ", text)
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    text = text.strip().lower()

    if not text:
        return ""

    collapsed = _SEPARATORS.sub(separator, text)
    collapsed = re.sub(rf"{re.escape(separator)}+", separator, collapsed)
    return collapsed.strip(separator)


def normalize_module_name(name: str) -> str:
    """Return a valid Python module identifier from ``name``."""

    candidate = slugify(name, separator="_", allow_unicode=False)
    candidate = candidate.replace("-", "_")
    candidate = _INVALID_IDENTIFIER.sub("_", candidate)
    candidate = _MULTIPLE_UNDERSCORES.sub("_", candidate)
    candidate = candidate.strip("_")

    if not candidate:
        candidate = "project"

    if candidate[0].isdigit():
        candidate = f"_{candidate}"

    return candidate


def normalize_class_name(name: str) -> str:
    """Return a canonical class name generated from ``name``."""

    collapsed = _collapse_whitespace(name)
    if not collapsed:
        return "Project"

    words = re.split(r"[\s_\-]+", collapsed)
    return "".join(word.capitalize() for word in words if word)
