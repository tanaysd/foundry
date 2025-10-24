"""Generate a concise review brief for pull requests."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence

from scripts.ci.diff_api_surface import (
    ApiDiff,
    compute_api_diff,
    render_markdown as render_api_markdown,
    snapshot_from_directory,
    snapshot_from_git,
)

CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = CURRENT_FILE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TASK_PATTERN = re.compile(r"TC-(\d+(?:-\d+)?)", re.IGNORECASE)
ISSUE_CLOSING_PATTERN = re.compile(r"(Closes|Fixes|Resolves)\s+#(\d+)", re.IGNORECASE)
GENERIC_ISSUE_PATTERN = re.compile(r"#(\d+)")
HIGH_RISK_PREFIXES = (
    "src/foundry/core/adapters/",
    "src/foundry/runtime/",
    "src/foundry/eval/",
)
COVERAGE_THRESHOLD = 85.0


class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class PRMetadata:
    title: str
    body: str
    html_url: str | None = None


@dataclass(frozen=True)
class CoverageReport:
    overall_percent: float | None
    file_percentages: Mapping[str, float]


@dataclass(frozen=True)
class CoverageEntry:
    path: str
    percent: float
    delta: float | None
    is_low: bool


@dataclass
class CoverageSummary:
    overall_percent: float | None
    entries: List[CoverageEntry]
    missing_files: List[str]
    warnings: List[str]
    has_report: bool
    has_base_report: bool


@dataclass
class BriefSections:
    task_card: str
    issue_link: str | None
    risk: RiskLevel
    changed_files: List[str]
    scope_summary: List[str]
    coverage: CoverageSummary
    api_diff: ApiDiff
    api_markdown: str
    contract_files: List[str]
    notes: List[str]


def normalize_repo_path(path: str, repo_root: Path | None = None) -> str:
    candidate = Path(path)
    if repo_root is not None:
        try:
            candidate = candidate.relative_to(repo_root)
        except ValueError:
            pass
    normalized = candidate.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def detect_task_card(*texts: str) -> str:
    for text in texts:
        for match in TASK_PATTERN.finditer(text or ""):
            return match.group(0).upper()
    return "Not detected"


def extract_issue_number(text: str) -> int | None:
    closing = ISSUE_CLOSING_PATTERN.search(text or "")
    if closing:
        return int(closing.group(2))
    generic = GENERIC_ISSUE_PATTERN.search(text or "")
    if generic:
        return int(generic.group(1))
    return None


def classify_risk(changed_paths: Sequence[str]) -> RiskLevel:
    normalized = [normalize_repo_path(path) for path in changed_paths]
    for path in normalized:
        for prefix in HIGH_RISK_PREFIXES:
            if path.startswith(prefix):
                return RiskLevel.HIGH
    for path in normalized:
        if path.startswith("src/"):
            return RiskLevel.MEDIUM
    return RiskLevel.LOW


def summarize_scope(changed_paths: Sequence[str], limit: int = 10) -> List[str]:
    counter: Dict[str, int] = {}
    for path in changed_paths:
        normalized = normalize_repo_path(path)
        parent = Path(normalized).parent.as_posix()
        if not parent or parent == ".":
            parent = Path(normalized).name
        counter[parent] = counter.get(parent, 0) + 1

    if not counter:
        return ["No files changed."]

    sorted_items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    entries = [
        f"- `{directory}` ({count} file{'s' if count != 1 else ''})"
        for directory, count in sorted_items[:limit]
    ]
    if len(sorted_items) > limit:
        remaining = len(sorted_items) - limit
        entries.append(f"- …and {remaining} more directories")
    return entries


def _coverage_from_element(root: ET.Element, repo_root: Path) -> CoverageReport:
    overall_text = root.attrib.get("line-rate")
    overall = float(overall_text) * 100 if overall_text is not None else None
    files: Dict[str, float] = {}
    for class_el in root.findall(".//class"):
        filename = class_el.attrib.get("filename")
        if not filename:
            continue
        try:
            line_rate = float(class_el.attrib.get("line-rate", "0"))
        except ValueError:
            line_rate = 0.0
        normalized = normalize_repo_path(filename, repo_root)
        files[normalized] = line_rate * 100
    return CoverageReport(overall, files)


def parse_coverage_xml(path: Path, repo_root: Path) -> CoverageReport | None:
    if not path.exists():
        return None
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return None
    return _coverage_from_element(tree.getroot(), repo_root)


def parse_coverage_content(content: str, repo_root: Path) -> CoverageReport | None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    return _coverage_from_element(root, repo_root)


def gather_coverage_summary(
    changed_paths: Sequence[str],
    report: CoverageReport | None,
    base_report: CoverageReport | None,
    threshold: float = COVERAGE_THRESHOLD,
) -> CoverageSummary:
    if report is None:
        missing = {
            normalize_repo_path(path)
            for path in changed_paths
            if normalize_repo_path(path).endswith(".py")
        }
        return CoverageSummary(
            overall_percent=None,
            entries=[],
            missing_files=sorted(missing),
            warnings=[],
            has_report=False,
            has_base_report=base_report is not None,
        )

    entries: List[CoverageEntry] = []
    warnings: List[str] = []
    missing: set[str] = set()
    base_percentages = base_report.file_percentages if base_report else {}

    for path in changed_paths:
        normalized = normalize_repo_path(path)
        if not normalized.endswith(".py"):
            continue
        percent = report.file_percentages.get(normalized)
        if percent is None:
            missing.add(normalized)
            continue
        delta = None
        if normalized in base_percentages:
            delta = percent - base_percentages[normalized]
        is_low = percent < threshold
        if is_low:
            warnings.append(
                f"`{normalized}` coverage {percent:.2f}% (<{threshold:.0f}%)"
            )
        entries.append(CoverageEntry(normalized, percent, delta, is_low))

    entries.sort(key=lambda entry: entry.path)
    sorted_missing = sorted(missing)
    return CoverageSummary(
        overall_percent=report.overall_percent,
        entries=entries,
        missing_files=sorted_missing,
        warnings=warnings,
        has_report=True,
        has_base_report=base_report is not None,
    )


def render_coverage_section(summary: CoverageSummary) -> str:
    if not summary.has_report:
        return "Coverage report not found. Run pytest with --cov to generate coverage.xml."

    lines: List[str] = []
    if summary.overall_percent is not None:
        lines.append(f"Overall coverage: {summary.overall_percent:.2f}%")

    if summary.entries:
        if summary.has_base_report:
            lines.append("")
            lines.append("| File | Coverage | Δ |")
            lines.append("| --- | --- | --- |")
            for entry in summary.entries:
                delta_display = (
                    f"{entry.delta:+.2f}%" if entry.delta is not None else "—"
                )
                lines.append(
                    f"| `{entry.path}` | {entry.percent:.2f}% | {delta_display} |"
                )
        else:
            lines.append("")
            lines.append("| File | Coverage |")
            lines.append("| --- | --- |")
            for entry in summary.entries:
                lines.append(f"| `{entry.path}` | {entry.percent:.2f}% |")

    if summary.missing_files:
        lines.append("")
        lines.append(
            "Missing coverage data for: "
            + ", ".join(f"`{path}`" for path in summary.missing_files)
        )

    if summary.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in summary.warnings:
            lines.append(f"- ⚠️ {warning}")

    if not lines:
        lines.append("No coverage data for changed files.")

    return "\n".join(lines)


def list_contract_files(changed_paths: Sequence[str]) -> List[str]:
    contracts: List[str] = []
    for path in changed_paths:
        normalized = normalize_repo_path(path)
        if normalized.startswith("tests/contracts/"):
            contracts.append(normalized)
    return sorted(set(contracts))


def fetch_pr_metadata(
    repo: str,
    pr_number: int,
    token: str | None,
    opener: Callable[[urllib.request.Request], Any] | None = None,
) -> PRMetadata | None:
    if not repo or pr_number <= 0:
        return None
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    opener_func = opener if opener is not None else urllib.request.urlopen
    try:
        with opener_func(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        return None
    return PRMetadata(
        title=payload.get("title", ""),
        body=payload.get("body") or "",
        html_url=payload.get("html_url"),
    )


def load_base_coverage(base_ref: str, repo_root: Path) -> CoverageReport | None:
    try:
        result = subprocess.run(
            ["git", "show", f"{base_ref}:coverage.xml"],
            cwd=repo_root,
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    return parse_coverage_content(result.stdout, repo_root)


def list_changed_files(base_ref: str, head_ref: str, repo_root: Path) -> List[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"],
            cwd=repo_root,
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def build_api_diff(repo_root: Path, base_ref: str) -> tuple[ApiDiff, str]:
    base_snapshot = snapshot_from_git(base_ref, repo_root)
    head_snapshot = snapshot_from_directory(repo_root / "src")
    diff = compute_api_diff(base_snapshot, head_snapshot)
    return diff, render_api_markdown(diff)


def build_brief_sections(
    repo_root: Path,
    base_ref: str,
    metadata: PRMetadata,
    changed_files: List[str],
    coverage_path: Path,
    repo_name: str,
) -> BriefSections:
    risk = classify_risk(changed_files)
    scope = summarize_scope(changed_files)
    coverage_report = parse_coverage_xml(coverage_path, repo_root)
    base_coverage = load_base_coverage(base_ref, repo_root)
    coverage_summary = gather_coverage_summary(changed_files, coverage_report, base_coverage)
    api_diff, api_markdown = build_api_diff(repo_root, base_ref)
    contracts = list_contract_files(changed_files)

    notes: List[str] = []
    if not changed_files:
        notes.append("No file changes detected between base and head commits.")
    for warning in coverage_summary.warnings:
        notes.append(f"Coverage warning — {warning}")
    if coverage_summary.missing_files and coverage_summary.has_report:
        notes.append(
            "ℹ️ Missing coverage data for "
            + ", ".join(f"`{path}`" for path in coverage_summary.missing_files)
        )
    if not coverage_summary.has_report:
        notes.append("ℹ️ coverage.xml not found; coverage section includes guidance.")

    task_card = detect_task_card(metadata.title, metadata.body)
    issue_number = extract_issue_number(metadata.body)
    issue_link: str | None = None
    if issue_number and repo_name:
        issue_link = f"https://github.com/{repo_name}/issues/{issue_number}"

    return BriefSections(
        task_card=task_card,
        issue_link=issue_link,
        risk=risk,
        changed_files=changed_files,
        scope_summary=scope,
        coverage=coverage_summary,
        api_diff=api_diff,
        api_markdown=api_markdown,
        contract_files=contracts,
        notes=notes,
    )


def render_brief(sections: BriefSections) -> str:
    lines: List[str] = ["## Review Brief", ""]

    lines.append("### Task")
    lines.append(f"- **Task Card:** {sections.task_card}")
    if sections.issue_link:
        lines.append(f"- **Linked Issue:** [{sections.issue_link}]({sections.issue_link})")
    else:
        lines.append("- **Linked Issue:** Not detected")
    lines.append("")

    lines.append("### Risk")
    lines.append(f"- **Level:** {sections.risk.value}")
    lines.append(f"- **Changed files:** {len(sections.changed_files)}")
    lines.append("")

    lines.append("### Scope")
    lines.extend(sections.scope_summary or ["No files changed."])
    lines.append("")

    lines.append("### Coverage")
    lines.append(render_coverage_section(sections.coverage))
    lines.append("")

    lines.append("### API changes")
    lines.append(sections.api_markdown or "No public API changes detected.")
    lines.append("")

    lines.append("### Contracts")
    if sections.contract_files:
        for contract in sections.contract_files:
            lines.append(f"- `{contract}`")
    else:
        message = "No contract tests changed."
        if sections.risk is RiskLevel.HIGH:
            message += " High-risk change — run `pytest tests/contracts` for safety."
        lines.append(message)
    lines.append("")

    lines.append("### Notes")
    if sections.notes:
        for note in sections.notes:
            lines.append(f"- {note}")
    else:
        lines.append("- No additional notes.")

    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Base commit SHA")
    parser.add_argument("--head", required=True, help="Head commit SHA")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="GitHub repository in the form owner/name.",
    )
    parser.add_argument(
        "--coverage", default="coverage.xml", help="Path to coverage XML report."
    )
    parser.add_argument("--pr-title", default=None, help="Override PR title")
    parser.add_argument("--pr-body", default=None, help="Override PR body")
    parser.add_argument(
        "--workdir",
        default=str(Path.cwd()),
        help="Repository working directory (defaults to CWD).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def load_metadata(args: argparse.Namespace) -> PRMetadata:
    if args.pr_title is not None or args.pr_body is not None:
        return PRMetadata(title=args.pr_title or "", body=args.pr_body or "")
    token = os.environ.get("GITHUB_TOKEN")
    metadata = fetch_pr_metadata(args.repo, args.pr, token)
    if metadata is None:
        return PRMetadata(title="", body="")
    return metadata


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.workdir).resolve()
    metadata = load_metadata(args)
    changed_files = list_changed_files(args.base, args.head, repo_root)
    coverage_path = repo_root / args.coverage
    sections = build_brief_sections(
        repo_root=repo_root,
        base_ref=args.base,
        metadata=metadata,
        changed_files=changed_files,
        coverage_path=coverage_path,
        repo_name=args.repo,
    )
    print(render_brief(sections))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
