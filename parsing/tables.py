from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
TIME_RE = re.compile(r"\b(\d{1,2})\s*[hH]\s*(\d{2})?\b")
VERSION_RE = re.compile(r"\b(VOST|VF)\b", re.IGNORECASE)


def is_table_line(line: str) -> bool:
    if "|" not in line:
        return False
    if TABLE_SEPARATOR_RE.match(line):
        return False
    return True


def parse_table_line(line: str) -> Optional[List[str]]:
    if not is_table_line(line):
        return None
    parts = [p.strip() for p in line.strip().strip("|").split("|")]
    if len(parts) < 2:
        return None
    return parts


def iter_lines_with_rows(page_text: str) -> Iterable[Tuple[str, Optional[List[str]]]]:
    for raw_line in page_text.splitlines():
        line = (raw_line or "").strip()
        if not line:
            continue
        yield line, parse_table_line(line)


def _format_time(hh: str, mm: Optional[str]) -> str:
    h = int(hh)
    if mm:
        return f"{h}h{mm}"
    return f"{h}h"


def parse_time_cell(cell_text: str) -> List[Tuple[str, Optional[str]]]:
    if not cell_text:
        return []

    t = cell_text.upper().replace("*", " ")

    times: List[Tuple[str, Optional[str]]] = []
    for m in TIME_RE.finditer(t):
        time_str = _format_time(m.group(1), m.group(2))
        version: Optional[str] = None

        # Prefer an explicit version immediately after the time (e.g. "20h VOST")
        after = t[m.end():m.end() + 8]
        after_match = VERSION_RE.search(after)
        if after_match:
            version = after_match.group(1)
        else:
            # Or immediately before the time (e.g. "VOST 20h")
            before = t[max(0, m.start() - 8):m.start()]
            before_match = VERSION_RE.search(before)
            if before_match:
                version = before_match.group(1)

        times.append((time_str, version))

    return times
