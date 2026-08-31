# preprocessing/citation_extraction (Phase 0 - Person A)

Extracts citation references (AIR/SCC/SCR formats) from each domain corpus.

## Run (after retrieval/keyword_retrieval/retrieve_domains.py)
```
python preprocessing/citation_extraction/extract_citations.py
```

## Formats handled
- **AIR**: `AIR 1978 SC 597`, `AIR1982SC149` (no spaces), `AIR 1962 Patna 255` (non-SC courts too)
- **SCC**: `(1973) 4 SCC 225`, `1981 SCC (2) 460`
- **SCR**: `[1974] 3 SCR 379`, `1978 (2) SCR 621`

## Self-citation exclusion
Every judgment's own citation appears once in an "Equivalent citations:"
header line near the top - excluded automatically so it doesn't create a
self-loop edge in the graph later.

## Output (data/processed/citations/)
One CSV per domain: `citing_file_name, citing_year, citation_type,
citation_raw, citation_normalized`

Validated on real 1980-81 test data: 1,319 citation mentions extracted
from 525/799 judgments, correctly typed and normalized across bracket
format variants.

## Bug found and fixed during Phase 1 testing
Judgments repeat their own citation in TWO places: the "Equivalent
citations:" line, and a separate "CITATION:" metadata field further down
(found in ~55% of judgments). The original exclusion only handled the
first, so self-citations from the second field were wrongly counted as
citations to another case - producing self-loop edges (a judgment "citing
itself") once resolved in Phase 1. Fixed by excluding the entire header
zone (first 800 characters) rather than just the one labeled line.
Verified: self-loops dropped from present to 0 after the fix.

## Known limitation
Occasional PDF-extraction artifacts (e.g. a `]` character rendered as `1`
by the source PDF) can produce a slightly garbled citation. This is a
source-data quality issue inherited from the PDF corpus, not a bug in
this script - worth a one-line mention in your report's limitations, not
worth chasing down case by case.

## Next step (Phase 1)
`citation_normalized` values here are NOT yet resolved against actual
judgment files - that happens in `network/citation_network/`, which
matches these normalized citation strings back to `citing_file_name`
values across the corpus to build real citing -> cited edges.
