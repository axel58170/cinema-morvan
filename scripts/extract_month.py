#!/usr/bin/env python3
"""Monthly extraction pipeline: OCR -> screenings -> movies.json -> data.js."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parse_program import extract_all, PDF_PATH


def main() -> int:
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else PDF_PATH
    screenings, movies = extract_all(pdf_path)

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    data_path = Path("data.js")
    movies_path = Path("movies.json")
    movies_js_path = Path("movies.js")

    data_path.write_text(
        "window.PROGRAM_LAST_UPDATED = \"" + stamp + "\";\n" +
        "window.PROGRAM = " + json.dumps(screenings, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    movies_path.write_text(
        json.dumps(movies, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    movies_js_path.write_text(
        "window.MOVIES = " + json.dumps(movies, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
