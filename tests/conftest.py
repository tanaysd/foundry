from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests.fixtures import openai_fake

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def patch_openai_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure OpenAI streaming uses deterministic fake fixtures."""

    monkeypatch.setattr(
        "foundry.core.adapters.openai.create_openai_stream",
        openai_fake.create_openai_stream,
    )
