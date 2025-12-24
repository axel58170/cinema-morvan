from __future__ import annotations

import os
from typing import Any, Dict, List

from api_clients import call_mistral_ocr


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


def extract_raw_texts(pdf_path: str) -> List[str]:
    ocr_json = call_mistral_ocr(pdf_path)
    return collect_page_texts(ocr_json)


try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()
else:
    _load_env_fallback()
