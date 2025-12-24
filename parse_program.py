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

import json
import os
from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple
from api_clients import fetch_tmdb_details
from ocr.mistral import extract_raw_texts
from parsing.screenings import parse_screenings, screenings_to_records
from rules.rules import Rules, ScreeningRecord, apply_rules, load_rules
from movies.blurbs import build_movies_from_texts

PDF_PATH = "INTERNET-MORVAN.pdf"  # adjust if needed

# ---- OCR ----


def normalize_texts(texts: List[str]) -> List[str]:
    return texts

def records_to_dicts(records: List[ScreeningRecord], include_tmdb: bool) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for r in records:
        item = {
            "cinema": r.cinema,
            "movie_title": r.movie_title,
            "date": r.date,
            "time": r.time,
            "version": r.version,
        }
        if include_tmdb:
            item["original_title"] = r.original_title
            item["original_language"] = r.original_language
            item["yt_trailer_url"] = r.yt_trailer_url
        output.append(item)
    return output


# ---- Main ----

def build_screenings_from_texts(
    texts: List[str],
    tmdb_key: str,
    rules: Rules,
) -> List[Dict[str, Any]]:
    screenings = parse_screenings(texts)
    records = screenings_to_records(screenings)

    if not tmdb_key:
        records = apply_rules(records, rules)
        return records_to_dicts(records, include_tmdb=False)

    info_cache: Dict[str, Dict[str, Optional[str]]] = {}
    enriched: List[ScreeningRecord] = []
    for record in records:
        title = record.movie_title or ""
        if title not in info_cache:
            info_cache[title] = fetch_tmdb_details(title, tmdb_key)
        info = info_cache[title]
        enriched.append(
            replace(
                record,
                original_title=info.get("original_title"),
                original_language=info.get("original_language"),
                yt_trailer_url=info.get("yt_trailer_url"),
            )
        )

    enriched = apply_rules(enriched, rules)
    return records_to_dicts(enriched, include_tmdb=True)


def extract_screenings(pdf_path: str) -> List[Dict[str, Any]]:
    texts = normalize_texts(extract_raw_texts(pdf_path))
    tmdb_key = os.getenv("TMDB_API_KEY", "").strip()
    rules = load_rules("rules.json")
    return build_screenings_from_texts(texts, tmdb_key, rules)


def extract_all(pdf_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    texts = normalize_texts(extract_raw_texts(pdf_path))
    screenings = parse_screenings(texts)
    tmdb_key = os.getenv("TMDB_API_KEY", "").strip()
    rules = load_rules("rules.json")
    screenings_out = build_screenings_from_texts(texts, tmdb_key, rules)
    movies_out = build_movies_from_texts(texts, screenings, tmdb_key)
    return screenings_out, movies_out


if __name__ == "__main__":
    data = extract_screenings(PDF_PATH)
    print(json.dumps(data, ensure_ascii=False, indent=2))
