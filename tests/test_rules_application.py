import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rules.rules import Rules, ScreeningRecord, apply_rules


def test_apply_rules_cinema_alias():
    rules = Rules(cinema_aliases={"LUZY": "LUZY – Le Vox"}, title_fixes={}, version_rules={})
    record = ScreeningRecord(
        cinema="LUZY",
        movie_title="Film",
        date="2025-12-24",
        time="20h",
        version=None,
    )
    updated = apply_rules([record], rules)[0]
    assert updated.cinema == "LUZY – Le Vox"


def test_apply_rules_title_fix():
    rules = Rules(cinema_aliases={}, title_fixes={"Chasse gardée2": "Chasse gardée 2"}, version_rules={})
    record = ScreeningRecord(
        cinema="LUZY – Le Vox",
        movie_title="Chasse gardée2",
        date="2025-12-24",
        time="20h",
        version=None,
    )
    updated = apply_rules([record], rules)[0]
    assert updated.movie_title == "Chasse gardée 2"


def test_apply_rules_version_from_original_language():
    rules = Rules(
        cinema_aliases={},
        title_fixes={},
        version_rules={"set_vf_if_original_language_not_fr_and_not_vost": True},
    )
    record = ScreeningRecord(
        cinema="LUZY – Le Vox",
        movie_title="Film",
        date="2025-12-24",
        time="20h",
        version=None,
        original_language="en",
    )
    updated = apply_rules([record], rules)[0]
    assert updated.version == "VF"
