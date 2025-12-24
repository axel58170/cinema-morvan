from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ScreeningRecord:
    cinema: str
    movie_title: str
    date: str
    time: str
    version: Optional[str]
    original_title: Optional[str] = None
    original_language: Optional[str] = None
    yt_trailer_url: Optional[str] = None


@dataclass(frozen=True)
class Rules:
    cinema_aliases: Dict[str, str]
    title_fixes: Dict[str, str]
    version_rules: Dict[str, Any]


def load_rules(path: str) -> Rules:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return Rules(
        cinema_aliases=payload.get("cinema_aliases") or {},
        title_fixes=payload.get("title_fixes") or {},
        version_rules=payload.get("version_rules") or {},
    )


def apply_rules(records: List[ScreeningRecord], rules: Rules) -> List[ScreeningRecord]:
    updated: List[ScreeningRecord] = []
    for record in records:
        cinema = rules.cinema_aliases.get(record.cinema, record.cinema)
        title = rules.title_fixes.get(record.movie_title, record.movie_title)
        version = record.version

        if rules.version_rules.get("set_vf_if_original_language_not_fr_and_not_vost"):
            original_language = (record.original_language or "").lower()
            current_version = (version or "").upper()
            if original_language and original_language != "fr" and current_version != "VOST":
                version = "VF"

        updated.append(
            replace(
                record,
                cinema=cinema,
                movie_title=title,
                version=version,
            )
        )
    return updated
