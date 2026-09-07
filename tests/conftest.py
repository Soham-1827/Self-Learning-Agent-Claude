import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

FIXTURES = Path(__file__).parent / "fixtures"
VIDEO_ID = "9_SZFIW7tus"


@pytest.fixture
def meta():
    return json.loads((FIXTURES / f"{VIDEO_ID}.meta.json").read_text(encoding="utf-8"))


@pytest.fixture
def captions():
    return json.loads(
        (FIXTURES / f"{VIDEO_ID}.captions.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def description(meta):
    return meta["description"]
