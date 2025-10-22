from __future__ import annotations

import pytest

from foundry.naming import normalize_class_name, normalize_module_name, slugify


@pytest.mark.parametrize(
    "value, expected",
    [
        ("My Project", "my-project"),
        ("   My    Project  ", "my-project"),
        ("Project! @ 2025", "project-2025"),
        ("Café ☕", "cafe"),
        (("alpha", "beta"), "alpha-beta"),
    ],
)
def test_slugify_basic(value, expected):
    assert slugify(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("My Project", "my_project"),
        ("123 invalid", "_123_invalid"),
        ("Symbols*&^%", "symbols"),
        ("", "project"),
    ],
)
def test_normalize_module_name(value, expected):
    assert normalize_module_name(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("my project", "MyProject"),
        ("alreadyCamel", "Alreadycamel"),
        ("---", "Project"),
    ],
)
def test_normalize_class_name(value, expected):
    assert normalize_class_name(value) == expected
