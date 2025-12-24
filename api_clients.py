from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

MODEL = "mistral-ocr-latest"
OCR_ENDPOINT = "https://api.mistral.ai/v1/ocr"
TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


def load_pdf_base64(path: str) -> str:
    with open(path, "rb") as handle:
        return base64.b64encode(handle.read()).decode("ascii")


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
