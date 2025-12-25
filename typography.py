from __future__ import annotations

import re

# Narrow no-break space used by French typography.
NARROW_NBSP = "\u202F"

# Matches any regular or non-breaking space.
_SPACE_RE = re.compile(r"[ \u00A0\u202F]+")

# Punctuation that should be preceded by a narrow no-break space in French.
_FRENCH_PUNCT_RE = re.compile(r"[;:!?»]")

# Insert/normalize a narrow no-break space after the opening guillemet.
_AFTER_OPEN_QUOTE_RE = re.compile(r"«[ \u00A0\u202F]*")

# Normalize runs of three dots into an ellipsis character.
_ELLIPSIS_RE = re.compile(r"\.\.\.")


def _normalize_space_before_punct(text: str) -> str:
    # Ensure French punctuation is preceded by a narrow no-break space.
    # This replaces any existing spaces (regular or NBSP) before ;:!?».
    result = []
    i = 0
    for match in re.finditer(r"[ \u00A0\u202F]*[;:!?»]", text):
        start = match.start()
        end = match.end()
        punct = text[end - 1]
        if start == 0:
            # Do not insert a leading space at the very beginning of the string.
            result.append(text[i:end])
        else:
            result.append(text[i:start])
            result.append(NARROW_NBSP + punct)
        i = end
    result.append(text[i:])
    return "".join(result)


def normalize_french_typography(text: str) -> str:
    """
    Normalize French typography for OCR-extracted text.

    - Use narrow no-break spaces before ;:!?» and after «
    - Normalize ellipsis from '...' to '…'
    - Keep apostrophes and straight quotes untouched
    - Idempotent and safe for already-normalized text
    """
    if not text:
        return text

    # Decode common HTML entity before punctuation spacing normalization.
    # Prevents '&amp;' from turning into '&\u202F;'.
    text = text.replace("&amp;", "&")

    # Normalize three dots into a single ellipsis character.
    text = _ELLIPSIS_RE.sub("…", text)

    # Insert/normalize spacing after opening guillemet.
    # French typography requires a narrow no-break space after «.
    text = _AFTER_OPEN_QUOTE_RE.sub("«" + NARROW_NBSP, text)

    # Ensure proper narrow no-break space before French punctuation.
    text = _normalize_space_before_punct(text)

    return text


if __name__ == "__main__":
    # Basic sanity checks (doctest-style asserts).
    assert normalize_french_typography("Attention!") == "Attention\u202F!"
    assert normalize_french_typography("Pourquoi ?") == "Pourquoi\u202F?"
    assert normalize_french_typography("«Bonjour»") == "«\u202FBonjour\u202F»"
    assert normalize_french_typography("Film : titre") == "Film\u202F: titre"
    assert normalize_french_typography("Un titre...") == "Un titre…"
    assert normalize_french_typography("A &amp; B;") == "A & B\u202F;"
    # Idempotency
    sample = "«\u202FBonjour\u202F»"
    assert normalize_french_typography(sample) == sample
