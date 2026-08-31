"""
Stage: preprocessing/citation_extraction (Phase 0 of Person A's track)

Extracts citation references (AIR/SCC/SCR formats) from each domain corpus.
Excludes each judgment's OWN citation (found in its "Equivalent citations:"
header line) so we don't create a self-loop in the graph.

Run (after retrieval/keyword_retrieval/retrieve_domains.py):
    python preprocessing/citation_extraction/extract_citations.py

Output: one CSV per domain in data/processed/citations/, listing every
citation reference found in each judgment's body text.
"""

import sys
import os
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from tqdm import tqdm

from config.paths import DATA_FINAL, DATA_PROCESSED

CITATIONS_OUT_DIR = os.path.join(DATA_PROCESSED, "citations")
os.makedirs(CITATIONS_OUT_DIR, exist_ok=True)

DOMAIN_FILES = {
    "Financial Fraud": "financial_fraud_corpus.csv",
    "Corruption": "corruption_corpus.csv",
    "Digital Financial Fraud": "digital_financial_fraud_corpus.csv",
}

# Matches: AIR1982SC149, AIR 1981 SC 344, AIR\n1961 SC 4931
AIR_PATTERN = re.compile(r"AIR\s*(\d{4})\s*([A-Za-z]{2,6})\s*(\d+)", re.IGNORECASE)

# Matches: (1980)3SCC625, (1973) 4 SCC 225, 1981 SCC (1) 108
SCC_PATTERN = re.compile(
    r"\(?(\d{4})\)?\s*(\d{1,2})?\s*SCC\s*(?:\((\d+)\))?\s*(\d+)", re.IGNORECASE
)

# Matches: [1981]1SCR206, 1978 (2) SCR 621, 1982(2)SCR 365
SCR_PATTERN = re.compile(r"[\[\(]?(\d{4})[\]\)]?\s*\(?(\d+)?\)?\s*SCR\s*(\d+)", re.IGNORECASE)

# The header line containing the judgment's OWN citation (one of two places
# it appears - see HEADER_ZONE_CHARS below for the other).
SELF_CITATION_LINE = re.compile(r"Equivalent citations:.*", re.IGNORECASE)

# Indian Kanoon judgments repeat the judgment's own citation TWICE near the
# top: once in "Equivalent citations:" and again in a separate "CITATION:"
# metadata field a bit further down (found in ~55% of judgments). Rather
# than enumerate every possible header field name, exclude the whole
# header zone - the real judgment body never starts this early.
HEADER_ZONE_CHARS = 800


def get_self_citation_span(text: str):
    m = SELF_CITATION_LINE.search(text)
    return (m.start(), m.end()) if m else None


def in_self_citation_line(pos: int, span) -> bool:
    if pos < HEADER_ZONE_CHARS:
        return True
    if span is None:
        return False
    return span[0] <= pos < span[1]


def normalize_citation(citation_type: str, match) -> str:
    """Standardizes spacing/case so the same citation in different formats
    (e.g. 'AIR1982SC149' vs 'AIR 1982 SC 149') maps to one canonical string."""
    parts = [p for p in match.groups() if p]
    return f"{citation_type} " + " ".join(parts).upper()


def extract_citations_from_text(text: str):
    if not isinstance(text, str) or not text:
        return []

    self_span = get_self_citation_span(text)
    results = []

    for pattern, ctype in [(AIR_PATTERN, "AIR"), (SCC_PATTERN, "SCC"), (SCR_PATTERN, "SCR")]:
        for m in pattern.finditer(text):
            if in_self_citation_line(m.start(), self_span):
                continue
            results.append({
                "citation_type": ctype,
                "citation_raw": m.group(0).strip(),
                "citation_normalized": normalize_citation(ctype, m),
            })

    return results


def process_domain(domain_name: str, filename: str):
    path = os.path.join(DATA_FINAL, filename)
    if not os.path.exists(path):
        print(f"Skipping {domain_name} - file not found: {path}")
        return

    df = pd.read_csv(path)
    print(f"\n{domain_name}: {len(df)} judgments")

    rows = []
    for _, r in tqdm(df.iterrows(), total=len(df), desc=domain_name):
        citations = extract_citations_from_text(r["text"])
        for c in citations:
            rows.append({
                "citing_file_name": r["file_name"],
                "citing_year": r["year"],
                "citation_type": c["citation_type"],
                "citation_raw": c["citation_raw"],
                "citation_normalized": c["citation_normalized"],
            })

    out_df = pd.DataFrame(rows)
    out_path = os.path.join(CITATIONS_OUT_DIR, f"{domain_name.lower().replace(' ', '_')}_citations.csv")
    out_df.to_csv(out_path, index=False)

    unique_cases_citing = out_df["citing_file_name"].nunique() if len(out_df) else 0
    print(f"  {len(out_df)} citation mentions found, from {unique_cases_citing}/{len(df)} judgments")
    print(f"  Saved -> {out_path}")


def main():
    for domain_name, filename in DOMAIN_FILES.items():
        process_domain(domain_name, filename)


if __name__ == "__main__":
    main()
