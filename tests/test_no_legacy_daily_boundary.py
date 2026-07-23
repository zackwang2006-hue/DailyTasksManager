from pathlib import Path
import re


LEGACY_BOUNDARY_PATTERNS = (
    re.compile(r"(?<!\d)0" + "4" + r":00"),
    re.compile(r"(?<!\d)" + "4" + r":00"),
    re.compile(r"(?<!\d)0" + "3" + r":59"),
    re.compile(r"(?<!\d)" + "3" + r":59"),
    re.compile(r"time\(\s*" + "4" + r"\s*,\s*0"),
    re.compile(r"time\(\s*" + "3" + r"\s*,\s*59"),
    re.compile(r"hours\s*=\s*" + "4"),
    re.compile(r"hour\s*=\s*" + "4"),
)


def test_no_legacy_4am_daily_boundary_logic():
    root = Path(__file__).resolve().parents[1]
    paths = [
        *root.joinpath("app").rglob("*.py"),
        *root.joinpath("tests").rglob("*.py"),
        root / "README.md",
        root / "CHANGELOG.md",
    ]

    matches = []
    for path in paths:
        if path == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in LEGACY_BOUNDARY_PATTERNS:
            if pattern.search(text):
                matches.append(f"{path.relative_to(root)} contains {pattern.pattern}")

    assert matches == []
