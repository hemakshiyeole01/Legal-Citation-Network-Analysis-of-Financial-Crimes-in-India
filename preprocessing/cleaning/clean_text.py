"""
Stage: preprocessing/cleaning

Strips boilerplate noise from raw extracted text - mainly the repeated
Indian Kanoon page footer ("Indian Kanoon - http://indiankanoon.org/doc/12345/ 3")
that appears on every page and pollutes keyword/citation matching if left in.

Run (after extraction/pdf_extraction/combine_years.py):
    python preprocessing/cleaning/clean_text.py
"""

import sys
import os
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from config.paths import DATA_PROCESSED

INPUT_FILE = os.path.join(DATA_PROCESSED, "all_judgments_raw_text.csv")
OUTPUT_FILE = os.path.join(DATA_PROCESSED, "all_judgments_cleaned.csv")

# Matches: "Indian Kanoon - http://indiankanoon.org/doc/12345/ 3"
FOOTER_PATTERN = re.compile(r"Indian Kanoon\s*-\s*http://indiankanoon\.org/doc/\d+/?\s*\d*")

# Collapse repeated blank lines/whitespace left behind after footer removal
WHITESPACE_PATTERN = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = FOOTER_PATTERN.sub("", text)
    text = WHITESPACE_PATTERN.sub("\n\n", text)
    return text.strip()


def main():
    df = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df)} judgments")

    before_avg = df["char_count"].mean()

    df["text"] = df["text"].apply(clean_text)
    df["char_count"] = df["text"].str.len()

    after_avg = df["char_count"].mean()
    print(f"Avg char_count before cleaning: {before_avg:.0f}")
    print(f"Avg char_count after cleaning:  {after_avg:.0f}")
    print(f"Removed ~{before_avg - after_avg:.0f} chars/doc on average (footer noise)")

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
