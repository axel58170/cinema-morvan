from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

WEEKDAY_RE = re.compile(r"\b(MER|JEU|VEN|SAM|DIM|LUN|MAR)\b", re.IGNORECASE)
DAYNUM_RE = re.compile(r"\b([0-3]?\d)\b")

MONTH_MAP = {
    "JAN": 1, "JANVIER": 1,
    "FEV": 2, "FÉV": 2, "FEVRIER": 2, "FÉVRIER": 2,
    "MAR": 3, "MARS": 3,
    "AVR": 4, "AVRIL": 4,
    "MAI": 5,
    "JUN": 6, "JUIN": 6,
    "JUI": 7, "JUILLET": 7,
    "AOU": 8, "AOÛ": 8, "AOUT": 8, "AOÛT": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBRE": 9,
    "OCT": 10, "OCTOBRE": 10,
    "NOV": 11, "NOVEMBRE": 11,
    "DEC": 12, "DÉC": 12, "DECEMBRE": 12, "DÉCEMBRE": 12,
}

WEEK_RANGE_RE = re.compile(
    r"DU\s+\d+\s+AU\s+\d+\s+([A-ZÉÛ]+)",
    re.IGNORECASE,
)


@dataclass
class ParseContext:
    current_cinema: Optional[str] = None
    col_idx_to_iso: Dict[int, str] = None
    current_month: Optional[int] = None

    def __post_init__(self) -> None:
        if self.col_idx_to_iso is None:
            self.col_idx_to_iso = {}


def infer_month_from_week_range(text: str) -> Optional[int]:
    if not text:
        return None
    m = WEEK_RANGE_RE.search(text.upper())
    if not m:
        return None
    token = m.group(1)
    return MONTH_MAP.get(token)


def parse_header_cells_to_daynums(header_row_texts: List[str]) -> List[Optional[int]]:
    out: List[Optional[int]] = []
    for t in header_row_texts:
        if not t:
            out.append(None)
            continue
        if not WEEKDAY_RE.search(t):
            out.append(None)
            continue
        m = DAYNUM_RE.search(t)
        out.append(int(m.group(1)) if m else None)
    return out


def daynums_to_dates(
    daynums: List[Optional[int]],
    year: int,
    month: Optional[int],
) -> Dict[int, str]:
    idx_to_iso: Dict[int, str] = {}

    if month is None:
        return idx_to_iso

    nums = [n for n in daynums if n is not None]
    if not nums:
        return idx_to_iso

    has_large = any(n >= 24 for n in nums)
    has_small = any(n <= 7 for n in nums)

    prev_month = 12 if month == 1 else month - 1

    for idx, n in enumerate(daynums):
        if n is None:
            continue
        if has_large and has_small and n >= 24:
            m = prev_month
        else:
            m = month
        try:
            idx_to_iso[idx] = date(year, m, n).isoformat()
        except ValueError:
            # Lossless handling: skip invalid day/month combos from OCR noise.
            continue

    return idx_to_iso
