# extraction/pdf_extraction

Converts downloaded PDF judgments into text, one CSV per year.

## Run (after extraction/download completes)
```
python extraction/pdf_extraction/extract_text.py
python extraction/pdf_extraction/combine_years.py
```

## Behavior
- `extract_text.py` processes one year folder at a time, saves a CSV per
  year to `data/extracted/`, and skips years already processed - safe to
  stop and resume.
- `combine_years.py` merges all per-year CSVs into
  `data/processed/all_judgments_raw_text.csv`.

## Output columns
`file_name, year, text, char_count`

`char_count == 0` means extraction failed for that PDF (scanned/image-only
PDF, corrupt file, etc.) - check these separately later if the failure
count is high.
