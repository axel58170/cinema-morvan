from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from api_clients import fetch_tmdb_details
from parsing.screenings import Screening


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
