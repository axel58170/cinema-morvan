import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import parse_program as pp
from ocr import mistral


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_program_smoke(monkeypatch):
    sample_ocr = json.loads((FIXTURES_DIR / "sample_ocr.json").read_text())
    expected = json.loads((FIXTURES_DIR / "expected_output.json").read_text())

    monkeypatch.setenv("TMDB_API_KEY", "")
    monkeypatch.setattr(mistral, "call_mistral_ocr", lambda _path: sample_ocr)

    result = pp.extract_screenings("sample.pdf")
    assert result == expected
