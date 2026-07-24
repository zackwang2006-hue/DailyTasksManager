"""Application version loaded from the single project VERSION source."""

import sys
from pathlib import Path


def _version_file() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "VERSION"
    return Path(__file__).resolve().parents[1] / "VERSION"


APP_VERSION = _version_file().read_text(encoding="utf-8").strip()
