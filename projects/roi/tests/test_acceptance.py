"""Every acceptance criterion in docs/acceptance.md is checked by a test, and tests cite only real ones."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_criterion_has_a_test() -> None:
    listed = set(
        re.findall(
            r"^- \*\*([A-Z]+-\d+)\*\*",
            (ROOT / "docs/acceptance.md").read_text(),
            re.MULTILINE,
        )
    )
    cited: set[str] = set()
    for path in (ROOT / "tests").glob("test_*.py"):
        for args in re.findall(r"@pytest\.mark\.criteria\(([^)]*)\)", path.read_text()):
            cited.update(re.findall(r'"([A-Z]+-\d+)"', args))
    assert listed, "no criteria found"
    assert sorted(listed - cited) == [], "criteria with no test"
    assert sorted(cited - listed) == [], "tests citing unknown criteria"
