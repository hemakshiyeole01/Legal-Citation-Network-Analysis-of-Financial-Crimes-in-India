"""
Stage: retrieval/keyword_retrieval (validation helper, read-only)

Quick look at one domain's corpus without opening the big CSV in an editor:
year spread, how many judgments predate a cutoff year, which subcategories
drive the matches, and a list of the early judgments so you can eyeball them.

Run:
    python retrieval/keyword_retrieval/inspect_domain.py "Digital Financial Fraud"
    python retrieval/keyword_retrieval/inspect_domain.py "Digital Financial Fraud" --before 2000
    python retrieval/keyword_retrieval/inspect_domain.py "Violent Crime / Homicide" --before 1960
"""

import sys
import os
import re
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd

from config.paths import DATA_FINAL, ONTOLOGY_PATH
from config.domains import get_domains, corpus_filename


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", help='e.g. "Digital Financial Fraud"')
    parser.add_argument("--before", type=int, default=2000,
                        help="list judgments with year before this (default 2000)")
    args = parser.parse_args()

    if args.domain not in get_domains():
        sys.exit(f"Unknown domain '{args.domain}'. Choose from: {get_domains()}")

    path = os.path.join(DATA_FINAL, corpus_filename(args.domain))
    wanted = ["file_name", "year", "domain_hit_totals", "matched_domains", "matched_subcategories"]
    cols = [c for c in pd.read_csv(path, nrows=0).columns if c in wanted]
    df = pd.read_csv(path, usecols=cols)  # skip the huge text column
    df["year"] = df["year"].astype(int)

    print(f"{args.domain}: {len(df)} judgments")
    if df.empty:
        return

    print(f"Years: min {df.year.min()} | median {int(df.year.median())} | max {df.year.max()}")

    print("\nBy decade:")
    print(df.groupby((df.year // 10) * 10).size().to_string())

    early = df[df.year < args.before].sort_values("year")
    print(f"\nJudgments before {args.before}: {len(early)} of {len(df)}")

    # matched_subcategories lists EVERY subcategory that passed for the
    # judgment, including ones from other domains (kept for audit). Split
    # them so you can see what is actually driving THIS domain.
    onto = pd.read_csv(ONTOLOGY_PATH, usecols=["crime_category", "subcategory"])
    home = onto.set_index("subcategory")["crime_category"].to_dict()
    subcats = (df["matched_subcategories"].str.split("; ").explode()
               .str.replace(r"\s*\[\d+ hits?\]", "", regex=True).str.strip())
    own = subcats[subcats.map(home) == args.domain]
    other = subcats[subcats.map(home) != args.domain]
    print(f"\nThis domain's own subcategories (a judgment can carry several):")
    print(own.value_counts().to_string() if len(own) else "  (none)")
    if len(other):
        print("\nOther domains' subcategories also present in these judgments:")
        print(other.value_counts().to_string())

    if "matched_domains" in df:
        multi = df["matched_domains"].str.contains(";", na=False).sum()
        print(f"\nAlso assigned to another domain: {multi} of {len(df)}")

    if len(early):
        print(f"\nEarly judgments to eyeball (first 25):")
        for _, r in early.head(25).iterrows():
            totals = r.get("domain_hit_totals", "")
            print(f"  {r.year}  {r.file_name[:70]}")
            print(f"        {r.matched_subcategories}   | totals: {totals}")


if __name__ == "__main__":
    main()
