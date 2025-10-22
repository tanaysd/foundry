from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from foundry.cli import _parse_key_value_pairs, main


def test_parse_key_value_pairs():
    context = _parse_key_value_pairs(["name=demo", "version=1.0"])
    assert context == {"name": "demo", "version": "1.0"}

    with pytest.raises(argparse.ArgumentTypeError):
        _parse_key_value_pairs(["invalid"])


def test_cli_init_creates_project(tmp_path: Path):
    project_dir = tmp_path / "output"
    exit_code = main(["init", "My Project", "--directory", str(project_dir)])
    assert exit_code == 0
    assert (project_dir / "README.md").exists()


def test_cli_render_writes_to_output(tmp_path: Path):
    template_path = tmp_path / "template.txt"
    template_path.write_text("Hello {{ name }}", encoding="utf-8")
    output_path = tmp_path / "output.txt"
    exit_code = main(
        [
            "render",
            str(template_path),
            "-c",
            "name=world",
            "-o",
            str(output_path),
            "--missing",
            "error",
        ]
    )
    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == "Hello world"
