Prompt 1 (Page 1 only)

You are extracting structured data from a regional cinema programme PDF.

Task: Extract all individual screenings that appear on PAGE 1 ONLY. Do not use or infer anything from other pages.

Return JSON only. The root must be a JSON array. No markdown, no explanations.

Schema for each screening object:
• cinema: string (full cinema name as printed)
• movie_title: string (clean title only; remove durations and stray times)
• date: YYYY-MM-DD (ISO date; weeks run Wed→Tue; use any “Du … au … ” ranges on page 1 to resolve month/day; if year is not printed, assume 2025 unless the page clearly indicates another year)
• time: Hh or HhMM (e.g. 20h, 18h30)
• version: “VF” or “VOST” (VOST if explicitly stated near that screening; otherwise VF)

Normalization rules:
• One JSON object per screening time (if multiple times on the same day, emit multiple objects).
• Preserve accents.
• Do not include duplicates.

Start now: process PAGE 1 ONLY and output the JSON array.

Prompt 2 (Page 2 only)

You are extracting structured data from a regional cinema programme PDF.

Task: Extract all individual screenings that appear on PAGE 2 ONLY. Do not use or infer anything from other pages.

Return JSON only. The root must be a JSON array. No markdown, no explanations.

Schema for each screening object:
• cinema: string (full cinema name as printed)
• movie_title: string (clean title only; remove durations and stray times)
• date: YYYY-MM-DD (ISO date; weeks run Wed→Tue; use any “Du … au … ” ranges on page 2 to resolve month/day; if year is not printed, assume 2025 unless the page clearly indicates another year)
• time: Hh or HhMM (e.g. 20h, 18h30)
• version: “VF” or “VOST” (VOST if explicitly stated near that screening; otherwise VF)

Normalization rules:
• One JSON object per screening time (if multiple times on the same day, emit multiple objects).
• Preserve accents.
• Do not include duplicates.

Start now: process PAGE 2 ONLY and output the JSON array.

Merge prompt (third turn)

Take the two JSON arrays from the previous two messages (page 1 and page 2). Merge them into one JSON array, removing duplicates where duplicates are defined as identical (cinema, movie_title, date, time, version). Output JSON only.
