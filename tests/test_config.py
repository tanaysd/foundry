from __future__ import annotations

import pytest

from foundry.config import ProjectConfig


def test_from_name_generates_expected_identifiers():
    config = ProjectConfig.from_name("My Cool App", description="Utilities for demos")
    assert config.name == "My Cool App"
    assert config.slug == "my-cool-app"
    assert config.package == "my_cool_app"
    assert config.class_name == "MyCoolApp"
    assert config.description == "Utilities for demos"


def test_from_name_rejects_empty_input():
    with pytest.raises(ValueError):
        ProjectConfig.from_name("   ")


def test_context_includes_defaults():
    config = ProjectConfig.from_name("Demo")
    context = config.context()
    assert context["name"] == "Demo"
    assert context["slug"] == "demo"
    assert context["package_name"] == "demo"
    assert context["class_name"] == "Demo"
    assert context["description"].startswith("TODO")
