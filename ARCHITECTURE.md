# Architecture

This project splits parsing into small, focused modules with a thin orchestration layer.

Pipeline (high level)

PDF
→ OCR (`ocr/`)
→ parsing (context + tables → screenings) (`parsing/`)
→ rules (post-parse corrections) (`rules/`)
→ movies (blurbs + TMDB enrichment) (`movies/`)
→ JSON output

Modules

- `ocr/mistral.py`
  - Loads OCR text from Mistral and returns per-page text blocks.
- `parsing/context.py`
  - Calendar logic and parsing context state (month/day resolution).
- `parsing/tables.py`
  - Table row detection + time parsing.
- `parsing/screenings.py`
  - Core schedule parser producing `Screening` objects.
- `rules/rules.py`
  - Loads `rules.json` and applies post-parse corrections.
- `movies/blurbs.py`
  - Extracts blurbs and enriches with TMDB metadata.
- `parse_program.py`
  - Orchestrates the pipeline and emits output.
