from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from parsing.context import (
    ParseContext,
    WEEKDAY_RE,
    infer_month_from_week_range,
    parse_header_cells_to_daynums,
    daynums_to_dates,
)
from parsing.tables import iter_lines_with_rows, parse_time_cell
from rules.rules import ScreeningRecord

DEFAULT_YEAR = 2025


@dataclass(frozen=True)
class Screening:
    cinema: str
    movie_title: str
    date: str       # YYYY-MM-DD
    time: str       # e.g. 20h30
    version: Optional[str]  # VF, VOST, or None


def normalize_cinema(raw: str) -> Optional[str]:
    if not raw:
        return None

    t = raw.upper()
    t = re.sub(r"[^A-ZÀ-ÖØ-Ý ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    if "LUZY" in t:
        return "LUZY – Le Vox"
    if "CHATEAU" in t or "CHÂTEAU" in t:
        return "CHÂTEAU-CHINON – L’Étoile"
    if "OUROUX" in t or "MORVAN" in t:
        return "OUROUX-EN-MORVAN – Le Clap"
    if "BAINS" in t:
        return "SAINT-HONORÉ-LES-BAINS – Le Sélect"

    return None


def normalize_title(raw: str) -> str:
    t = (raw or "").strip()
    t = re.sub(r"\s*-\s*\d+h\d{2}\b.*$", "", t).strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _update_context_from_text(
    page_text: str,
    context: ParseContext,
) -> None:
    if not page_text:
        return
    month = infer_month_from_week_range(page_text)
    if month:
        context.current_month = month


def _update_context_from_row(
    row: List[str],
    context: ParseContext,
    year: int,
) -> Optional[Dict[int, str]]:
    row_joined = " ".join(row)
    month_from_row = infer_month_from_week_range(row_joined)
    if month_from_row:
        context.current_month = month_from_row

    if any(WEEKDAY_RE.search(c or "") for c in row):
        daynums = parse_header_cells_to_daynums(row)
        if context.current_month is None:
            return {}
        return daynums_to_dates(daynums, year=year, month=context.current_month)

    return None


def _parse_screenings_from_row(
    row: List[str],
    context: ParseContext,
) -> List[Screening]:
    if not context.current_cinema or not context.col_idx_to_iso:
        return []
    title = normalize_title(row[0]) if row else ""
    if not title:
        return []

    results: List[Screening] = []
    for col_idx in range(1, len(row)):
        if col_idx not in context.col_idx_to_iso:
            continue
        cell_text = row[col_idx].strip()
        if not cell_text:
            continue
        times = parse_time_cell(cell_text)
        if not times:
            continue
        iso_date = context.col_idx_to_iso[col_idx]
        for time_str, version in times:
            results.append(
                Screening(
                    cinema=context.current_cinema,
                    movie_title=title,
                    date=iso_date,
                    time=time_str,
                    version=version,
                )
            )
    return results


def process_tables(texts: List[str], year: int) -> List[Screening]:
    results: List[Screening] = []

    context = ParseContext()

    for page_text in texts:
        if not page_text:
            continue

        _update_context_from_text(page_text, context)

        for line, row in iter_lines_with_rows(page_text):
            month_from_line = infer_month_from_week_range(line)
            if month_from_line:
                context.current_month = month_from_line

            cinema_from_line = normalize_cinema(line)
            if cinema_from_line:
                context.current_cinema = cinema_from_line
                continue

            if not row:
                continue

            maybe_idx_to_iso = _update_context_from_row(row, context, year)
            if maybe_idx_to_iso is not None:
                context.col_idx_to_iso = maybe_idx_to_iso
                continue

            maybe_cinema = normalize_cinema(row[0]) if row else None
            if maybe_cinema:
                context.current_cinema = maybe_cinema
                continue

            results.extend(_parse_screenings_from_row(row, context))

    return results


def parse_screenings(texts: List[str]) -> List[Screening]:
    return process_tables(texts, year=DEFAULT_YEAR)


def screenings_to_records(screenings: List[Screening]) -> List[ScreeningRecord]:
    uniq: Dict[Tuple[str, str, str, str, Optional[str]], Screening] = {}
    for s in screenings:
        key = (s.cinema, s.movie_title, s.date, s.time, s.version)
        uniq[key] = s
    return [
        ScreeningRecord(
            cinema=s.cinema,
            movie_title=s.movie_title,
            date=s.date,
            time=s.time,
            version=s.version,
        )
        for s in uniq.values()
    ]
