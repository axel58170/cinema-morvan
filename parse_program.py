#!/usr/bin/env python3
"""
Lossless cinema schedule extractor using Mistral OCR.

Pipeline:
1) Send PDF to Mistral OCR API.
2) Parse OCR markdown into tables/rows.
3) Resolve dates from week headers + day columns.
4) Expand each time cell into individual screening objects.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.request
import urllib.parse
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

PDF_PATH = "INTERNET-MORVAN.pdf"  # adjust if needed
MODEL = "mistral-ocr-latest"
OCR_ENDPOINT = "https://api.mistral.ai/v1/ocr"
DEFAULT_YEAR = 2025
TMDB_API_BASE = "https://api.themoviedb.org/3"

def _load_env_fallback(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()
else:
    _load_env_fallback()


@dataclass(frozen=True)
class Screening:
    cinema: str
    movie_title: str
    date: str       # YYYY-MM-DD
    time: str       # e.g. 20h30
    version: Optional[str]  # VF, VOST, or None


# ---- OCR ----

def load_pdf_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def call_mistral_ocr(pdf_path: str, include_image_base64: bool = False) -> Dict[str, Any]:
    api_key = os.getenv("MISTRAL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY is required")

    pdf_b64 = load_pdf_base64(pdf_path)
    payload = {
        "model": MODEL,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{pdf_b64}",
        },
        "include_image_base64": bool(include_image_base64),
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OCR_ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _http_get_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _pick_trailer_url(videos_payload: Dict[str, Any]) -> Optional[str]:
    results = videos_payload.get("results") or []
    if not results:
        return None
    ranked = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("site") != "YouTube":
            continue
        key = item.get("key")
        if not key:
            continue
        kind = (item.get("type") or "").lower()
        rank = 2
        if kind == "trailer":
            rank = 0
        elif kind == "teaser":
            rank = 1
        ranked.append((rank, key))
    if not ranked:
        return None
    ranked.sort(key=lambda pair: pair[0])
    return f"https://www.youtube.com/watch?v={ranked[0][1]}"


def fetch_tmdb_info(title: str, api_key: str) -> Dict[str, Optional[str]]:
    if not title:
        return {"original_title": None, "original_language": None, "yt_trailer_url": None}

    query = urllib.parse.quote(title)
    search_url = (
        f"{TMDB_API_BASE}/search/movie?api_key={api_key}"
        f"&query={query}&include_adult=false&language=fr-FR"
    )
    try:
        payload = _http_get_json(search_url)
    except Exception:
        return {"original_title": None, "original_language": None, "yt_trailer_url": None}

    results = payload.get("results") or []
    if not results:
        return {"original_title": None, "original_language": None, "yt_trailer_url": None}

    first = results[0]
    if not isinstance(first, dict):
        return {"original_title": None, "original_language": None, "yt_trailer_url": None}

    movie_id = first.get("id")
    original_title = first.get("original_title")
    original_language = first.get("original_language")
    trailer_url = None

    if movie_id:
        videos_url = (
            f"{TMDB_API_BASE}/movie/{movie_id}/videos?api_key={api_key}"
            f"&language=fr-FR"
        )
        try:
            videos_payload = _http_get_json(videos_url)
            trailer_url = _pick_trailer_url(videos_payload)
        except Exception:
            trailer_url = None

    return {
        "original_title": original_title,
        "original_language": original_language,
        "yt_trailer_url": trailer_url,
    }


# ---- Parsing helpers ----

WEEKDAY_RE = re.compile(r"\b(MER|JEU|VEN|SAM|DIM|LUN|MAR)\b", re.IGNORECASE)
DAYNUM_RE = re.compile(r"\b([0-3]?\d)\b")

MONTH_MAP = {
    "JAN": 1, "JANVIER": 1,
    "FEV": 2, "FÉV": 2, "FEVRIER": 2, "FÉVRIER": 2,
    "MAR": 3, "MARS": 3,
    "AVR": 4, "AVRIL": 4,
    "MAI": 5,
    "JUI": 6, "JUIN": 6,
    "JUIL": 7, "JUILLET": 7,
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


TIME_RE = re.compile(r"\b(\d{1,2})\s*[hH]\s*(\d{2})?\b")
VERSION_RE = re.compile(r"\b(VOST|VF)\b", re.IGNORECASE)


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


# ---- Markdown table parsing ----

TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")


def iter_markdown_table_rows(markdown: str) -> Iterable[List[str]]:
    for line in markdown.splitlines():
        if "|" not in line:
            continue
        if TABLE_SEPARATOR_RE.match(line):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 2:
            continue
        yield parts


def collect_page_texts(ocr_json: Dict[str, Any]) -> List[str]:
    pages = ocr_json.get("pages") or []
    texts: List[str] = []
    for p in pages:
        if isinstance(p, dict):
            if p.get("markdown"):
                texts.append(p.get("markdown"))
            elif p.get("text"):
                texts.append(p.get("text"))
            elif p.get("content"):
                texts.append(p.get("content"))
    if not texts and ocr_json.get("document_annotation"):
        texts.append(ocr_json["document_annotation"])
    return texts


def parse_markdown_row_from_line(line: str) -> Optional[List[str]]:
    if "|" not in line:
        return None
    if TABLE_SEPARATOR_RE.match(line):
        return None
    parts = [p.strip() for p in line.strip().strip("|").split("|")]
    if len(parts) < 2:
        return None
    return parts


def process_tables(texts: List[str], year: int) -> List[Screening]:
    results: List[Screening] = []

    current_cinema: Optional[str] = None
    col_idx_to_iso: Dict[int, str] = {}
    current_month: Optional[int] = None

    for page_text in texts:
        if not page_text:
            continue

        m = infer_month_from_week_range(page_text)
        if m:
            current_month = m

        for raw_line in page_text.splitlines():
            line = (raw_line or "").strip()
            if not line:
                continue

            month_from_line = infer_month_from_week_range(line)
            if month_from_line:
                current_month = month_from_line

            cinema_from_line = normalize_cinema(line)
            if cinema_from_line:
                current_cinema = cinema_from_line
                continue

            row = parse_markdown_row_from_line(line)
            if not row:
                continue

            row_joined = " ".join(row)
            month_from_row = infer_month_from_week_range(row_joined)
            if month_from_row:
                current_month = month_from_row

            if any(WEEKDAY_RE.search(c or "") for c in row):
                daynums = parse_header_cells_to_daynums(row)
                if current_month is None:
                    col_idx_to_iso = {}
                else:
                    col_idx_to_iso = daynums_to_dates(daynums, year=year, month=current_month)
                continue

            maybe_cinema = normalize_cinema(row[0]) if row else None
            if maybe_cinema:
                current_cinema = maybe_cinema
                continue

            if not current_cinema or not col_idx_to_iso:
                continue

            title = normalize_title(row[0]) if row else ""
            if not title:
                continue

            for col_idx in range(1, len(row)):
                if col_idx not in col_idx_to_iso:
                    continue
                cell_text = row[col_idx].strip()
                if not cell_text:
                    continue
                times = parse_time_cell(cell_text)
                if not times:
                    continue
                iso_date = col_idx_to_iso[col_idx]
                for time_str, version in times:
                    results.append(
                        Screening(
                            cinema=current_cinema,
                            movie_title=title,
                            date=iso_date,
                            time=time_str,
                            version=version,
                        )
                    )

    return results


# ---- Main ----

def extract_screenings(pdf_path: str) -> List[Dict[str, Any]]:
    ocr_json = call_mistral_ocr(pdf_path)
    texts = collect_page_texts(ocr_json)
    screenings = process_tables(texts, year=DEFAULT_YEAR)

    uniq: Dict[Tuple[str, str, str, str, Optional[str]], Screening] = {}
    for s in screenings:
        key = (s.cinema, s.movie_title, s.date, s.time, s.version)
        uniq[key] = s

    output = [s.__dict__ for s in uniq.values()]

    tmdb_key = os.getenv("TMDB_API_KEY", "").strip()
    if not tmdb_key:
        return output

    info_cache: Dict[str, Dict[str, Optional[str]]] = {}
    for item in output:
        title = item.get("movie_title") or ""
        if title not in info_cache:
            info_cache[title] = fetch_tmdb_info(title, tmdb_key)
        info = info_cache[title]
        item["original_title"] = info.get("original_title")
        item["original_language"] = info.get("original_language")
        item["yt_trailer_url"] = info.get("yt_trailer_url")

        original_language = (item.get("original_language") or "").lower()
        version = (item.get("version") or "").upper()
        if original_language and original_language != "fr" and version != "VOST":
            item["version"] = "VF"

    return output


if __name__ == "__main__":
    data = extract_screenings(PDF_PATH)
    print(json.dumps(data, ensure_ascii=False, indent=2))
