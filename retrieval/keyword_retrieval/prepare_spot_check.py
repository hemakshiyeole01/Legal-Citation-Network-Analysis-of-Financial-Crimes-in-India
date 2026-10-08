"""
Stage: retrieval/keyword_retrieval (validation)
Step 10 of the project checklist: prepare a manual spot-check sample.

Pulls a random sample from each domain corpus, extracts a short text
snippet around the first matched signal (so you don't have to read full
judgments to review), and adds a blank 'label' column for you to fill in
manually with Yes / No / Uncertain.

Run (after retrieve_domains.py):
    python retrieval/keyword_retrieval/prepare_spot_check.py
"""

import sys
import os
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd

from config.paths import DATA_FINAL
from config.domains import get_domains, corpus_filename

SAMPLE_SIZE_PER_DOMAIN = 20
RANDOM_SEED = 42


def get_snippet(text: str, subcategory_field: str, window: int = 150) -> str:
    """Finds the first matched keyword/section mentioned in matched_subcategories
    and returns a short window of surrounding text for quick manual review."""
    if not isinstance(text, str) or not text:
        return ""

    # Pull the first subcategory name out of "Cheating [3 hits]; Bribery [2 hits]"
    first_match = subcategory_field.split(";")[0]
    first_match = re.sub(r"\s*\[\d+\s*hits?\]", "", first_match).strip()

    # Search for a rough anchor: just find the first occurrence of any word
    # from the subcategory name in the text as a fallback anchor point.
    text_lower = text.lower()
    for word in first_match.lower().split():
        if len(word) < 4:
            continue
        idx = text_lower.find(word)
        if idx != -1:
            start = max(0, idx - window)
            end = min(len(text), idx + window)
            return "..." + text[start:end].replace("\n", " ") + "..."

    return text[:300].replace("\n", " ") + "..."


def main():
    all_samples = []

    for domain in get_domains():
        path = os.path.join(DATA_FINAL, corpus_filename(domain))
        if not os.path.exists(path):
            print(f"Skipping {domain} - file not found: {path}")
            continue

        df = pd.read_csv(path)
        n = min(SAMPLE_SIZE_PER_DOMAIN, len(df))
        sample = df.sample(n=n, random_state=RANDOM_SEED)

        sample["snippet"] = sample.apply(
            lambda r: get_snippet(r["text"], r["matched_subcategories"]), axis=1
        )
        sample["domain"] = domain
        sample["label"] = ""  # fill manually: Yes / No / Uncertain
        sample["notes"] = ""  # optional: why you labeled it that way

        all_samples.append(
            sample[["domain", "file_name", "year", "matched_subcategories", "snippet", "label", "notes"]]
        )
        print(f"{domain}: sampled {n} judgments")

    combined = pd.concat(all_samples, ignore_index=True)
    combined = combined.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)  # shuffle

    out_path = os.path.join(DATA_FINAL, "spot_check_sample.csv")
    combined.to_csv(out_path, index=False)
    print(f"\nSaved {len(combined)} rows for manual review -> {out_path}")
    print("Open in VS Code (not Excel - snippets can be long), fill 'label' column with Yes/No/Uncertain.")


if __name__ == "__main__":
    main()
