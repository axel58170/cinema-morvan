import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parsing.context import ParseContext
from parsing.screenings import _parse_screenings_from_row, _update_context_from_row


def test_parse_screenings_from_row_expands_times():
    row = ["Film", "16h30 / 20h VOST"]
    mapping = {1: "2025-12-24"}
    context = ParseContext(current_cinema="LUZY – Le Vox", col_idx_to_iso=mapping)
    screenings = _parse_screenings_from_row(row, context)

    assert [s.time for s in screenings] == ["16h30", "20h"]
    assert [s.version for s in screenings] == [None, "VOST"]


def test_update_context_from_row_sets_date_mapping():
    row = ["MER 24", "JEU 25"]
    context = ParseContext(current_month=12)
    mapping = _update_context_from_row(row, context, 2025)

    assert context.current_month == 12
    assert mapping == {0: "2025-12-24", 1: "2025-12-25"}
