#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root and enter it
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# Keep repo root on sys.path for any tests that import local packages
export PYTHONPATH="${ROOT_DIR}"

# ---- Clean prior build/test artifacts that can confuse mypy/pytest ----
rm -rf build/ dist/ .mypy_cache/ .pytest_cache/ .ruff_cache/ *.egg-info

echo "== Ruff =="
ruff check .

echo "== Mypy =="
# Point mypy at 'src' only to avoid picking up build/lib duplicates.
# '--explicit-package-bases' keeps imports unambiguous in a src/ layout.
mypy src --explicit-package-bases

echo "== Pytest (TC-06 adapter contract & parity) =="
# Run just the TC-06 adapter tests (pattern can be adjusted as needed)
pytest -q -k "openai_adapter_"

echo "All TC-06 checks passed."
