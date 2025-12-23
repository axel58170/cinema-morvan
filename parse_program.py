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
import unicodedata
import urllib.request
import urllib.parse
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple
from difflib import SequenceMatcher

PDF_PATH = "INTERNET-MORVAN.pdf"  # adjust if needed
MODEL = "mistral-ocr-latest"
OCR_ENDPOINT = "https://api.mistral.ai/v1/ocr"
DEFAULT_YEAR = 2025
TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"

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


def _normalize_for_match(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _best_match_title(target: str, candidates: List[str]) -> Optional[str]:
    if not target or not candidates:
        return None
    target_norm = _normalize_for_match(target)
    best = None
    best_score = 0.0
    for cand in candidates:
        cand_norm = _normalize_for_match(cand)
        if not cand_norm:
            continue
        if target_norm == cand_norm:
            return cand
        score = SequenceMatcher(None, target_norm, cand_norm).ratio()
        if target_norm in cand_norm or cand_norm in target_norm:
            score = max(score, 0.9)
        if score > best_score:
            best_score = score
            best = cand
    if best_score >= 0.85:
        return best
    return None


def _format_duration(minutes: Optional[int]) -> Optional[str]:
    if not minutes:
        return None
    h = minutes // 60
    m = minutes % 60
    if m:
        return f"{h}h{m:02d}"
    return f"{h}h"


def fetch_tmdb_details(title: str, api_key: str) -> Dict[str, Optional[str]]:
    if not title:
        return {
            "original_title": None,
            "original_language": None,
            "yt_trailer_url": None,
            "director": None,
            "cast": None,
            "genre": None,
            "duration": None,
            "blurb": None,
            "release_date": None,
            "poster_url": None,
            "poster_url_w780": None,
            "backdrop_url": None,
            "source": None,
        }

    query = urllib.parse.quote(title)
    search_url = (
        f"{TMDB_API_BASE}/search/movie?api_key={api_key}"
        f"&query={query}&include_adult=false&language=fr-FR"
    )
    try:
        payload = _http_get_json(search_url)
    except Exception:
        return {
            "original_title": None,
            "original_language": None,
            "yt_trailer_url": None,
            "director": None,
            "cast": None,
            "genre": None,
            "duration": None,
            "blurb": None,
            "release_date": None,
            "poster_url": None,
            "poster_url_w780": None,
            "backdrop_url": None,
            "source": None,
        }

    results = payload.get("results") or []
    if not results:
        return {
            "original_title": None,
            "original_language": None,
            "yt_trailer_url": None,
            "director": None,
            "cast": None,
            "genre": None,
            "duration": None,
            "blurb": None,
            "release_date": None,
            "poster_url": None,
            "poster_url_w780": None,
            "backdrop_url": None,
            "source": None,
        }

    first = results[0]
    if not isinstance(first, dict):
        return {
            "original_title": None,
            "original_language": None,
            "yt_trailer_url": None,
            "director": None,
            "cast": None,
            "genre": None,
            "duration": None,
            "blurb": None,
            "release_date": None,
            "poster_url": None,
            "poster_url_w780": None,
            "backdrop_url": None,
            "source": None,
        }

    movie_id = first.get("id")
    original_title = first.get("original_title")
    original_language = first.get("original_language")
    trailer_url = None
    director = None
    cast = None
    genre = None
    duration = None
    blurb = first.get("overview")
    release_date = first.get("release_date")
    poster_url = None
    poster_url_w780 = None
    backdrop_url = None

    if movie_id:
        try:
            details_url = (
                f"{TMDB_API_BASE}/movie/{movie_id}?api_key={api_key}"
                f"&language=fr-FR&append_to_response=credits,videos"
            )
            details = _http_get_json(details_url)
            videos_payload = details.get("videos") or {}
            trailer_url = _pick_trailer_url(videos_payload)
            runtime = details.get("runtime")
            duration = _format_duration(runtime)
            release_date = details.get("release_date") or release_date
            poster_path = details.get("poster_path")
            backdrop_path = details.get("backdrop_path")
            if poster_path:
                poster_url = f"{TMDB_IMAGE_BASE}/w342{poster_path}"
                poster_url_w780 = f"{TMDB_IMAGE_BASE}/w780{poster_path}"
            if backdrop_path:
                backdrop_url = f"{TMDB_IMAGE_BASE}/w780{backdrop_path}"
            genres = details.get("genres") or []
            if genres:
                genre = ", ".join(g.get("name") for g in genres if g.get("name"))
            credits = details.get("credits") or {}
            crew = credits.get("crew") or []
            directors = [c.get("name") for c in crew if c.get("job") == "Director" and c.get("name")]
            if directors:
                director = ", ".join(directors)
            cast_list = credits.get("cast") or []
            top_cast = [c.get("name") for c in cast_list[:5] if c.get("name")]
            if top_cast:
                cast = ", ".join(top_cast)
        except Exception:
            trailer_url = None

    return {
        "original_title": original_title,
        "original_language": original_language,
        "yt_trailer_url": trailer_url,
        "director": director,
        "cast": cast,
        "genre": genre,
        "duration": duration,
        "blurb": blurb,
        "release_date": release_date,
        "poster_url": poster_url,
        "poster_url_w780": poster_url_w780,
        "backdrop_url": backdrop_url,
        "source": "tmdb",
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


def _is_title_candidate(line: str) -> bool:
    if not line:
        return False
    stripped = line.strip()
    stripped = stripped.lstrip("# ").strip()
    if not stripped:
        return False
    if "|" in stripped:
        return False
    if stripped.startswith("!["):
        return False
    if stripped.lower().startswith(("de ", "avec ")):
        return False
    if "http" in stripped.lower() or "www." in stripped.lower():
        return False
    if "€" in stripped:
        return False
    if len(stripped) < 3:
        return False
    ignore = {
        "DOCUMENTAIRES",
        "ÉVÉNEMENTS",
        "EVENEMENTS",
        "JEUNE PUBLIC & EN FAMILLE",
        "JEUNE PUBLIC",
        "CIN'ESPIÈGLE",
        "CIN'ESPIEGLE",
        "CINÉ-CONCERT",
        "CINE-CONCERT",
        "LES PIONNIERS DU CINEMA",
        "LES PIONNIERS DU CINÉMA",
        "CLAP CLASSIC",
        "SEANCE PATRIMOINE",
        "SEANCE PATRIMOINE",
        "FAITS DIVERS",
        "AVANT PREMIERE",
        "AVANT PREMIÈRE",
    }
    upper = stripped.upper()
    if upper in ignore or upper.startswith("AVANT PREMI"):
        return False
    letters = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", stripped)
    if not letters:
        return False
    upper_letters = [ch for ch in letters if ch.isupper()]
    ratio = len(upper_letters) / max(1, len(letters))
    return ratio >= 0.6


def _parse_meta_line(line: str) -> Dict[str, Optional[str]]:
    meta = {"director": None, "cast": None, "genre": None, "duration": None}
    if not line:
        return meta
    parts = [p.strip() for p in line.split(" - ") if p.strip()]
    duration_re = re.compile(r"\b\d+h(\d{2})?\b")
    for part in parts:
        if part.startswith("De "):
            meta["director"] = part.replace("De ", "").strip()
            continue
        if part.startswith("Avec "):
            meta["cast"] = part.replace("Avec ", "").strip()
            continue
        if duration_re.search(part):
            meta["duration"] = duration_re.search(part).group(0)
            continue
    # Genre is typically the last non-duration, non-credit part
    for part in reversed(parts):
        if part.startswith("De ") or part.startswith("Avec "):
            continue
        if duration_re.search(part):
            continue
        meta["genre"] = part
        break
    return meta


def extract_movie_blurbs(texts: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
    blurbs: Dict[str, Dict[str, Optional[str]]] = {}
    for page_text in texts:
        if not page_text:
            continue
        if "|" in page_text:
            # Skip program tables; blurbs live on the non-tabular pages.
            continue
        lines = page_text.splitlines()
        current_title = None
        current_meta = None
        buffer: List[str] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("!["):
                continue
            if _is_title_candidate(line):
                if current_title and current_meta:
                    blurbs[current_title] = {
                        "title": current_title,
                        "meta_raw": current_meta,
                        "blurb": " ".join(buffer).strip() if buffer else None,
                        **(_parse_meta_line(current_meta) if current_meta else {}),
                        "source": "pdf",
                    }
                current_title = line.lstrip("# ").strip()
                current_meta = None
                buffer = []
                continue
            if current_title:
                if current_meta is None and (line.startswith("De ") or " - " in line):
                    current_meta = line
                else:
                    buffer.append(line)
        if current_title and current_meta:
            blurbs[current_title] = {
                "title": current_title,
                "meta_raw": current_meta,
                "blurb": " ".join(buffer).strip() if buffer else None,
                **(_parse_meta_line(current_meta) if current_meta else {}),
                "source": "pdf",
            }
    return blurbs


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

def build_screenings_from_texts(texts: List[str], tmdb_key: str) -> List[Dict[str, Any]]:
    screenings = process_tables(texts, year=DEFAULT_YEAR)

    uniq: Dict[Tuple[str, str, str, str, Optional[str]], Screening] = {}
    for s in screenings:
        key = (s.cinema, s.movie_title, s.date, s.time, s.version)
        uniq[key] = s

    output = [s.__dict__ for s in uniq.values()]

    if not tmdb_key:
        return output

    info_cache: Dict[str, Dict[str, Optional[str]]] = {}
    for item in output:
        title = item.get("movie_title") or ""
        if title not in info_cache:
            info_cache[title] = fetch_tmdb_details(title, tmdb_key)
        info = info_cache[title]
        item["original_title"] = info.get("original_title")
        item["original_language"] = info.get("original_language")
        item["yt_trailer_url"] = info.get("yt_trailer_url")

        original_language = (item.get("original_language") or "").lower()
        version = (item.get("version") or "").upper()
        if original_language and original_language != "fr" and version != "VOST":
            item["version"] = "VF"

    return output


def extract_screenings(pdf_path: str) -> List[Dict[str, Any]]:
    ocr_json = call_mistral_ocr(pdf_path)
    texts = collect_page_texts(ocr_json)
    tmdb_key = os.getenv("TMDB_API_KEY", "").strip()
    return build_screenings_from_texts(texts, tmdb_key)


def build_movies_from_texts(
    texts: List[str],
    screenings: List[Screening],
    tmdb_key: str,
) -> List[Dict[str, Any]]:
    screening_titles = sorted({s.movie_title for s in screenings if s.movie_title})

    blurbs = extract_movie_blurbs(texts)
    blurb_titles = list(blurbs.keys())

    tmdb_cache: Dict[str, Dict[str, Optional[str]]] = {}

    movies: List[Dict[str, Any]] = []
    for title in screening_titles:
        matched = _best_match_title(title, blurb_titles)
        blurb_info = blurbs.get(matched) if matched else None
        tmdb_info: Dict[str, Optional[str]] = {}
        if tmdb_key:
            if title not in tmdb_cache:
                tmdb_cache[title] = fetch_tmdb_details(title, tmdb_key)
            tmdb_info = tmdb_cache[title]

        entry: Dict[str, Any] = {
            "movie_title": title,
            "original_title": tmdb_info.get("original_title"),
            "original_language": tmdb_info.get("original_language"),
            "director": None,
            "cast": None,
            "genre": None,
            "duration": None,
            "blurb": None,
            "source": None,
            "yt_trailer_url": tmdb_info.get("yt_trailer_url"),
            "release_date": tmdb_info.get("release_date"),
            "poster_url": tmdb_info.get("poster_url"),
            "poster_url_w780": tmdb_info.get("poster_url_w780"),
            "backdrop_url": tmdb_info.get("backdrop_url"),
        }

        if blurb_info:
            entry.update({
                "director": blurb_info.get("director"),
                "cast": blurb_info.get("cast"),
                "genre": blurb_info.get("genre"),
                "duration": blurb_info.get("duration"),
                "blurb": blurb_info.get("blurb"),
                "source": "pdf",
            })
        elif tmdb_info:
            entry.update({
                "director": tmdb_info.get("director"),
                "cast": tmdb_info.get("cast"),
                "genre": tmdb_info.get("genre"),
                "duration": tmdb_info.get("duration"),
                "blurb": tmdb_info.get("blurb"),
                "release_date": tmdb_info.get("release_date"),
                "poster_url": tmdb_info.get("poster_url"),
                "poster_url_w780": tmdb_info.get("poster_url_w780"),
                "backdrop_url": tmdb_info.get("backdrop_url"),
                "source": "tmdb",
            })
        movies.append(entry)

    return movies


def extract_all(pdf_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ocr_json = call_mistral_ocr(pdf_path)
    texts = collect_page_texts(ocr_json)
    screenings = process_tables(texts, year=DEFAULT_YEAR)
    tmdb_key = os.getenv("TMDB_API_KEY", "").strip()
    screenings_out = build_screenings_from_texts(texts, tmdb_key)
    movies_out = build_movies_from_texts(texts, screenings, tmdb_key)
    return screenings_out, movies_out


if __name__ == "__main__":
    data = extract_screenings(PDF_PATH)
    print(json.dumps(data, ensure_ascii=False, indent=2))
