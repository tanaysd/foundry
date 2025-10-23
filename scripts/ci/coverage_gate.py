"""Warn when touched files fall below the expected coverage threshold."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Sequence

from scripts.ci.review_brief import COVERAGE_THRESHOLD, normalize_repo_path, parse_coverage_xml


def check_coverage(
    coverage_path: Path,
    files: Sequence[str],
    threshold: float,
    repo_root: Path,
) -> List[str]:
    report = parse_coverage_xml(coverage_path, repo_root)
    if report is None:
        return ["coverage.xml not found; skipping coverage gate warnings."]

    warnings: List[str] = []
    if files:
        normalized_files = sorted({normalize_repo_path(path) for path in files})
    else:
        normalized_files = sorted(report.file_percentages)
    for path in normalized_files:
        percent = report.file_percentages.get(path)
        if percent is None:
            warnings.append(f"No coverage data for `{path}`.")
            continue
        if percent < threshold:
            warnings.append(
                f"`{path}` coverage {percent:.2f}% (<{threshold:.0f}%)"
            )
    return warnings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", default="coverage.xml", help="Path to coverage XML file.")
    parser.add_argument(
        "--files",
        nargs="*",
        default=(),
        help="Touched files to evaluate (relative to repository root).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=COVERAGE_THRESHOLD,
        help="Coverage threshold percentage (defaults to 85).",
    )
    parser.add_argument(
        "--workdir",
        default=str(Path.cwd()),
        help="Repository root containing the coverage report.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.workdir).resolve()
    coverage_path = repo_root / args.coverage
    warnings = check_coverage(coverage_path, list(args.files), args.threshold, repo_root)
    if not warnings:
        print("All inspected files meet the coverage threshold.")
        return 0

    print("Coverage warnings:", file=sys.stderr)
    for warning in warnings:
        print(f"- {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
