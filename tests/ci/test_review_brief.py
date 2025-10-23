import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.review_brief import (  # noqa: E402
    PRMetadata,
    RiskLevel,
    build_brief_sections,
    classify_risk,
    list_changed_files,
    render_brief,
)


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_classify_risk_respects_priority() -> None:
    assert classify_risk(["src/foundry/runtime/engine.py"]) is RiskLevel.HIGH
    assert classify_risk(["src/other/module.py"]) is RiskLevel.MEDIUM
    assert classify_risk(["docs/index.md", "scripts/tool.py"]) is RiskLevel.LOW


def test_render_brief_includes_all_sections(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init")
    run_git(repo, "config", "user.email", "ci@example.com")
    run_git(repo, "config", "user.name", "CI Bot")

    write_file(
        repo / "src" / "pkg" / "service.py",
        """
from __future__ import annotations

def compute(value: int) -> int:
    return value + 1


class Worker:
    def operate(self, value: int) -> int:
        return value * 2
""".strip(),
    )
    write_file(
        repo / "coverage.xml",
        """
<?xml version='1.0'?>
<coverage line-rate="0.95">
  <packages>
    <package name="pkg" line-rate="0.95">
      <classes>
        <class name="pkg.service" filename="src/pkg/service.py" line-rate="1.0" />
      </classes>
    </package>
  </packages>
</coverage>
""".strip(),
    )
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "Base state")
    base_sha = run_git(repo, "rev-parse", "HEAD")

    write_file(
        repo / "src" / "pkg" / "service.py",
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
    write_file(
        repo / "src" / "pkg" / "api.py",
        """
from __future__ import annotations

def expose(flag: bool) -> bool:
    return flag
""".strip(),
    )
    write_file(
        repo / "tests" / "contracts" / "test_service.yaml",
        "contract: updated",
    )
    write_file(
        repo / "coverage.xml",
        """
<?xml version='1.0'?>
<coverage line-rate="0.9">
  <packages>
    <package name="pkg" line-rate="0.9">
      <classes>
        <class name="pkg.service" filename="src/pkg/service.py" line-rate="0.75" />
        <class name="pkg.api" filename="src/pkg/api.py" line-rate="0.92" />
      </classes>
    </package>
  </packages>
</coverage>
""".strip(),
    )
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "Feature update")
    head_sha = run_git(repo, "rev-parse", "HEAD")

    changed_files = list_changed_files(base_sha, head_sha, repo)
    metadata = PRMetadata(
        title="[TC-01-16] Improve service orchestration",
        body="Implements new API surface.\n\nCloses #42",
    )

    sections = build_brief_sections(
        repo_root=repo,
        base_ref=base_sha,
        metadata=metadata,
        changed_files=changed_files,
        coverage_path=repo / "coverage.xml",
        repo_name="example/project",
    )
    brief = render_brief(sections)

    assert "TC-01-16" in brief
    assert "https://github.com/example/project/issues/42" in brief
    assert "- **Level:** medium" in brief
    assert "tests/contracts/test_service.yaml" in brief
    assert "pkg.service.compute" in brief
    assert "Warnings" in brief
    assert "Coverage warning" in "\n".join(sections.notes)
    assert "75.00%" in brief
