from __future__ import annotations

from pathlib import Path

import pytest

from foundry.template import TemplateRenderer, TemplateRenderingError


@pytest.fixture()
def renderer() -> TemplateRenderer:
    return TemplateRenderer()


def test_render_string_with_filters(renderer: TemplateRenderer):
    template = "Project {{ name|title }} uses module {{ module_name|module }}"
    context = {"name": "sample app", "module_name": "Sample App"}
    rendered = renderer.render_string(template, context)
    assert rendered == "Project Sample App uses module sample_app"


def test_render_string_missing_policy_keep(renderer: TemplateRenderer):
    template = "Hello {{ missing }}"
    assert renderer.render_string(template, {}, missing="keep") == template


def test_render_string_missing_policy_empty(renderer: TemplateRenderer):
    template = "Hello {{ missing }}"
    assert renderer.render_string(template, {}, missing="empty") == "Hello "


def test_render_string_missing_policy_error(renderer: TemplateRenderer):
    with pytest.raises(TemplateRenderingError):
        renderer.render_string("{{ missing }}", {}, missing="error")


def test_render_file_round_trip(tmp_path: Path, renderer: TemplateRenderer):
    template_path = tmp_path / "template.txt"
    template_path.write_text("Name: {{ name }}", encoding="utf-8")
    output_path = tmp_path / "output.txt"
    renderer.render_file(template_path, {"name": "Demo"}, target=output_path)
    assert output_path.read_text(encoding="utf-8") == "Name: Demo"


def test_render_directory(tmp_path: Path, renderer: TemplateRenderer):
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "file.txt").write_text("{{ name }}", encoding="utf-8")
    target_dir = tmp_path / "output"
    renderer.render_directory(template_dir, target_dir, {"name": "Demo"})
    assert (target_dir / "file.txt").read_text(encoding="utf-8") == "Demo"


def test_unknown_filter_raises(renderer: TemplateRenderer):
    with pytest.raises(TemplateRenderingError):
        renderer.render_string("{{ name|unknown }}", {"name": "demo"})
