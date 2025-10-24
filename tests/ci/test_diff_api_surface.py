import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.diff_api_surface import (  # noqa: E402
    ApiDiff,
    compute_api_diff,
    render_markdown,
    snapshot_from_directory,
)


def write_module(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_compute_api_diff_detects_function_and_class_changes(tmp_path: Path) -> None:
    base_src = tmp_path / "base" / "src"
    head_src = tmp_path / "head" / "src"

    write_module(
        base_src / "pkg" / "service.py",
        """
from __future__ import annotations

def compute(value: int) -> int:
    return value + 1


class Worker:
    def operate(self, value: int) -> int:
        return value * 2
""".strip(),
    )
    write_module(
        base_src / "pkg" / "legacy.py",
        """
from __future__ import annotations

def legacy(name: str) -> str:
    return name.upper()
""".strip(),
    )

    write_module(
        head_src / "pkg" / "service.py",
        """
from __future__ import annotations

def compute(value: int, extra: int = 0) -> int:
    return value + extra


def helper(name: str) -> str:
    return name.title()


class Worker:
    def operate(self, value: int, factor: int = 1) -> int:
        return value * factor


class Coordinator:
    def dispatch(self, payload: str) -> str:
        return payload
""".strip(),
    )

    base_snapshot = snapshot_from_directory(base_src)
    head_snapshot = snapshot_from_directory(head_src)
    diff = compute_api_diff(base_snapshot, head_snapshot)

    assert "pkg.service.helper" in diff.added_functions
    assert diff.added_classes["pkg.service.Coordinator"] == {"dispatch": "(self, payload: str) -> str"}
    assert "pkg.legacy.legacy" in diff.removed_functions

    change = diff.changed_functions["pkg.service.compute"]
    assert change.previous == "(value: int) -> int"
    assert change.current == "(value: int, extra: int = 0) -> int"

    method_change = diff.changed_methods["pkg.service.Worker.operate"]
    assert method_change.previous == "(self, value: int) -> int"
    assert method_change.current == "(self, value: int, factor: int = 1) -> int"

    markdown = render_markdown(diff)
    assert "Added functions" in markdown
    assert "Removed functions" in markdown
    assert "Modified methods" in markdown


def test_render_markdown_without_changes_returns_placeholder() -> None:
    empty_diff = ApiDiff(
        added_functions={},
        removed_functions={},
        changed_functions={},
        added_classes={},
        removed_classes={},
        added_methods={},
        removed_methods={},
        changed_methods={},
    )
    assert render_markdown(empty_diff) == "No public API changes detected."
