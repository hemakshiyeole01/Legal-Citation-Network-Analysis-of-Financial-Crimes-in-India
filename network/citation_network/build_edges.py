"""
Stage: network/citation_network (Phase 1 of Person A's track)

Resolves the citation_normalized strings from Phase 0 against the actual
corpus to get real citing_file_name -> cited_file_name edges.

A cited case can be:
  - INTERNAL: in the same domain corpus (these build your actual graphs)
  - CROSS_DOMAIN: in a different one of your 3 domain corpora (interesting
    for cross-domain analysis - e.g. a Financial Fraud case citing a
    Corruption case)
  - OUTSIDE_DOMAINS: found in the full corpus but not in any of your 3
    domains (a landmark case unrelated to financial crime)
  - UNRESOLVED: not found anywhere in the full corpus (case outside the
    Kaggle dataset entirely, or a citation format quirk we couldn't match)

Run (after preprocessing/citation_extraction/extract_citations.py):
    python network/citation_network/build_edges.py
"""

import sys
import os
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "preprocessing", "citation_extraction"))

import pandas as pd
from tqdm import tqdm

from config.paths import DATA_PROCESSED, DATA_FINAL
from config.domains import get_domains, domain_to_filename, corpus_filename
from extract_citations import AIR_PATTERN, SCC_PATTERN, SCR_PATTERN, normalize_citation, SELF_CITATION_LINE

CITATIONS_DIR = os.path.join(DATA_PROCESSED, "citations")
FULL_CORPUS_PATH = os.path.join(DATA_PROCESSED, "all_judgments_cleaned.csv")
EDGES_OUT_DIR = os.path.join(os.path.dirname(__file__))


def extract_self_citations(text: str):
    """Pulls the judgment's OWN citation(s) from its 'Equivalent citations:'
    header line - the reverse of Phase 0, which excluded this line."""
    if not isinstance(text, str):
        return []

    m = SELF_CITATION_LINE.search(text)
    if not m:
        return []

    header_text = m.group(0)
    results = []
    for pattern, ctype in [(AIR_PATTERN, "AIR"), (SCC_PATTERN, "SCC"), (SCR_PATTERN, "SCR")]:
        for pm in pattern.finditer(header_text):
            results.append(normalize_citation(ctype, pm))
    return results


def build_citation_lookup():
    """Builds citation_normalized -> file_name using the FULL corpus (not
    just domain subsets), so cited cases outside the 3 domains still resolve."""
    print("Building citation lookup from full corpus...")
    full_df = pd.read_csv(FULL_CORPUS_PATH)

    lookup = {}
    for _, r in tqdm(full_df.iterrows(), total=len(full_df), desc="Indexing"):
        self_citations = extract_self_citations(r["text"])
        for c in self_citations:
            lookup[c] = r["file_name"]

    print(f"Lookup built: {len(lookup)} citation strings mapped to {full_df['file_name'].nunique()} judgments")
    return lookup


def load_domain_membership():
    """file_name -> set of domains. A judgment can legitimately match more
    than one domain (e.g. a case involving both cheating and bribery) - a
    plain dict overwrite here would silently lose that and misclassify
    edges for any multi-domain judgment."""
    membership = {}
    for domain in get_domains():
        path = os.path.join(DATA_FINAL, corpus_filename(domain))
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        for fname in df["file_name"]:
            membership.setdefault(fname, set()).add(domain)
    return membership


def classify_edge(citing_domain, cited_file_name, membership):
    if cited_file_name is None:
        return "UNRESOLVED"
    cited_domains = membership.get(cited_file_name)
    if not cited_domains:
        return "OUTSIDE_DOMAINS"
    if citing_domain in cited_domains:
        return "INTERNAL"
    return "CROSS_DOMAIN"


def main():
    lookup = build_citation_lookup()
    membership = load_domain_membership()

    for domain in get_domains():
        citations_path = os.path.join(
            CITATIONS_DIR, f"{domain_to_filename(domain)}_citations.csv"
        )
        if not os.path.exists(citations_path):
            print(f"Skipping {domain} - no citations file found")
            continue

        citations_df = pd.read_csv(citations_path)
        print(f"\n{domain}: resolving {len(citations_df)} citation mentions...")

        rows = []
        for _, r in citations_df.iterrows():
            cited_file = lookup.get(r["citation_normalized"])
            edge_type = classify_edge(domain, cited_file, membership)
            rows.append({
                "citing_file_name": r["citing_file_name"],
                "citing_domain": domain,
                "cited_citation_normalized": r["citation_normalized"],
                "cited_file_name": cited_file,
                "cited_domain": "; ".join(sorted(membership.get(cited_file, []))) if cited_file else None,
                "edge_type": edge_type,
            })

        edges_df = pd.DataFrame(rows)

        counts = edges_df["edge_type"].value_counts()
        total = len(edges_df)
        print(f"  INTERNAL:        {counts.get('INTERNAL', 0):5d} ({counts.get('INTERNAL', 0)/total*100:.1f}%)")
        print(f"  CROSS_DOMAIN:    {counts.get('CROSS_DOMAIN', 0):5d} ({counts.get('CROSS_DOMAIN', 0)/total*100:.1f}%)")
        print(f"  OUTSIDE_DOMAINS: {counts.get('OUTSIDE_DOMAINS', 0):5d} ({counts.get('OUTSIDE_DOMAINS', 0)/total*100:.1f}%)")
        print(f"  UNRESOLVED:      {counts.get('UNRESOLVED', 0):5d} ({counts.get('UNRESOLVED', 0)/total*100:.1f}%)")

        out_path = os.path.join(
            EDGES_OUT_DIR, f"{domain_to_filename(domain)}_edges_all.csv"
        )
        edges_df.to_csv(out_path, index=False)
        print(f"  Saved (all edge types) -> {out_path}")

        internal_only = edges_df[edges_df["edge_type"] == "INTERNAL"][
            ["citing_file_name", "cited_file_name"]
        ].drop_duplicates()
        internal_path = os.path.join(
            EDGES_OUT_DIR, f"{domain_to_filename(domain)}_edges_internal.csv"
        )
        internal_only.to_csv(internal_path, index=False)
        print(f"  Saved (internal only, deduped, for graph building) -> {internal_path}")


if __name__ == "__main__":
    main()
