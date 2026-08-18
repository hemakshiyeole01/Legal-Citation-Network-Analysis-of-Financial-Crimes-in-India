"""
Stage: retrieval/keyword_retrieval

Implements Steps 8-9 of the project checklist:
  Stage 1 (high recall): match judgments against ontology keywords + section
      numbers -> broad candidate pool per subcategory
  Stage 2 (precision filter): keep only matches where the signal appears
      more than once (proxy for "substantively discussed" vs "merely cited
      in passing", per the ontology's inclusion/exclusion rules), and for
      Digital Financial Fraud specifically, require a co-occurring
      financial-context term (per that domain's exclusion rule).

Run (after preprocessing/cleaning/clean_text.py):
    python retrieval/keyword_retrieval/retrieve_domains.py

Output: one CSV per domain in data/final/, plus a combined audit file
showing which subcategory(ies) each judgment matched.
"""

import sys
import os
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from tqdm import tqdm

from config.paths import DATA_PROCESSED, DATA_FINAL, ONTOLOGY_PATH

INPUT_FILE = os.path.join(DATA_PROCESSED, "all_judgments_cleaned.csv")

# Signal must appear at least this many times to count as "substantive"
# rather than a passing/incidental mention (Stage 2 precision rule).
MIN_OCCURRENCES_FOR_INCLUSION = 2

# Required for Digital Financial Fraud rows only (per ontology exclusion rule:
# a cyber-offence section alone isn't enough, it must involve money).
FINANCIAL_CONTEXT_TERMS = [
    "rupees", "rs.", "amount", "payment", "transaction", "bank account",
    "upi", "wallet", "transfer", "deposit", "withdrawal", "loss of",
    "cheated of", "fraudulently obtained", "money",
]

# Required (in addition to financial context) for Digital Financial Fraud.
# Without this, IPC 419/420 (used as a "supporting signal" per the ontology)
# alone would tag any ordinary cheating case as digital fraud - including
# judgments from before the IT Act existed (pre-2000).
DIGITAL_CONTEXT_TERMS = [
    "computer", "internet", "online", "cyber", "digital", "electronic",
    "website", "email", "information technology act", "it act",
    "server", "software", "otp", "sms",
]

# Act-name signal phrases, keyed by a short tag. Used to gate section-number
# matches: bare section numbers (e.g. PMLA's "3","4","5","8" or PCA's
# "7","8","9") are generic digits that appear in countless unrelated Acts.
# A section match only counts if the Act it belongs to is actually named
# somewhere in the document.
ACT_SIGNAL_PHRASES = {
    "ipc_bns": ["indian penal code", " ipc", "bharatiya nyaya sanhita", " bns"],
    "companies_act": ["companies act"],
    "pmla": ["prevention of money laundering act", "pmla", "money laundering act"],
    "cgst": ["cgst act", "goods and services tax act", "gst act", "central goods and services tax"],
    "pca": ["prevention of corruption act", " pca "],
    "it_act": ["information technology act", "it act"],
}


def detect_act_tags(act_field: str):
    """Given an ontology row's 'act' text, figure out which Act signal
    group(s) apply, so we know which phrases to require in the document."""
    act_lower = act_field.lower()
    tags = []
    if "ipc" in act_lower or "bns" in act_lower:
        tags.append("ipc_bns")
    if "companies act" in act_lower:
        tags.append("companies_act")
    if "pmla" in act_lower:
        tags.append("pmla")
    if "cgst" in act_lower:
        tags.append("cgst")
    if "pca" in act_lower or "prevention of corruption" in act_lower:
        tags.append("pca")
    if "it act" in act_lower:
        tags.append("it_act")
    return tags


def has_act_context(text_lower: str, act_tags) -> bool:
    """True if the document mentions at least one of the relevant Act names.
    If no tags were detected for this row (unmapped act), don't gate -
    fall back to keyword-only matching for that row."""
    if not act_tags:
        return True
    for tag in act_tags:
        phrases = ACT_SIGNAL_PHRASES.get(tag, [])
        if any(p in text_lower for p in phrases):
            return True
    return False


def load_ontology():
    df = pd.read_csv(ONTOLOGY_PATH)
    df.columns = [c.strip() for c in df.columns]
    return df


def extract_section_tokens(section_field: str):
    """
    Pulls individual section numbers out of a field like:
    'IPC 415, 417, 418, 419, 420; BNS 318, 319'
    Skips 4-digit tokens (those are Act years, e.g. 'Companies Act 2013').
    """
    raw_tokens = re.findall(r"\d+[A-Za-z]{0,2}(?:\(\d+\)(?:\([a-z]\))?)?", section_field)
    tokens = [t for t in raw_tokens if not re.fullmatch(r"\d{4}", t)]
    return list(set(tokens))


def build_section_patterns(tokens):
    """Builds regex patterns matching 'Section 420', 'Sec. 420', 'S. 420', 'u/s 420', etc."""
    patterns = []
    for token in tokens:
        escaped = re.escape(token)
        pattern = re.compile(
            rf"(?:section|sec\.?|s\.?|u/s)\s*{escaped}\b", re.IGNORECASE
        )
        patterns.append((token, pattern))
    return patterns


def build_keyword_patterns(keyword_field: str):
    keywords = [k.strip().lower() for k in keyword_field.split(",") if k.strip()]
    return keywords


def count_matches(text_lower: str, section_patterns, keywords, act_context_ok: bool):
    """Returns (total_occurrence_count, matched_signals list) for one row's rules.
    Section matches only count if act_context_ok (the relevant Act is actually
    named in the document) - otherwise bare section numbers like PMLA's
    "3","4","5","8" false-match against unrelated Acts."""
    total = 0
    matched_signals = []

    if act_context_ok:
        for token, pattern in section_patterns:
            hits = len(pattern.findall(text_lower))
            if hits:
                total += hits
                matched_signals.append(f"section:{token}({hits})")

        for kw in keywords:
            hits = text_lower.count(kw)
            if hits:
                total += hits
                matched_signals.append(f"kw:{kw}({hits})")

    return total, matched_signals


def has_financial_context(text_lower: str) -> bool:
    return any(term in text_lower for term in FINANCIAL_CONTEXT_TERMS)


def has_digital_context(text_lower: str) -> bool:
    return any(term in text_lower for term in DIGITAL_CONTEXT_TERMS)


def main():
    print("Loading ontology...")
    ontology = load_ontology()

    print("Loading cleaned judgments...")
    judgments = pd.read_csv(INPUT_FILE)
    judgments["text"] = judgments["text"].fillna("")
    print(f"Loaded {len(judgments)} judgments")

    # Precompute patterns for every ontology row once (not per-judgment)
    ontology_rules = []
    for _, row in ontology.iterrows():
        tokens = extract_section_tokens(str(row["section_for_retrieval"]))
        section_patterns = build_section_patterns(tokens)
        keywords = build_keyword_patterns(str(row["keywords"]))
        act_tags = detect_act_tags(str(row["act"]))
        ontology_rules.append({
            "crime_category": row["crime_category"],
            "subcategory": row["subcategory"],
            "section_patterns": section_patterns,
            "keywords": keywords,
            "act_tags": act_tags,
        })

    results = []

    for _, jrow in tqdm(judgments.iterrows(), total=len(judgments), desc="Classifying"):
        text_lower = jrow["text"].lower()
        matched_domains = set()
        matched_subcats = []

        for rule in ontology_rules:
            act_context_ok = has_act_context(text_lower, rule["act_tags"])
            total, signals = count_matches(
                text_lower, rule["section_patterns"], rule["keywords"], act_context_ok
            )

            if total < MIN_OCCURRENCES_FOR_INCLUSION:
                continue  # Stage 2: not substantive enough

            # Extra exclusion rules for Digital Financial Fraud:
            # requires BOTH a financial signal AND a genuine digital/cyber
            # signal, so ordinary IPC 419/420 cheating cases (used as a
            # supporting signal per the ontology) don't get mistagged as
            # digital fraud just because money is mentioned.
            if rule["crime_category"] == "Digital Financial Fraud":
                if not (has_financial_context(text_lower) and has_digital_context(text_lower)):
                    continue

            matched_domains.add(rule["crime_category"])
            matched_subcats.append(f"{rule['subcategory']} [{total} hits]")

        if matched_domains:
            results.append({
                "file_name": jrow["file_name"],
                "year": jrow["year"],
                "char_count": jrow["char_count"],
                "matched_domains": "; ".join(sorted(matched_domains)),
                "matched_subcategories": "; ".join(matched_subcats),
                "text": jrow["text"],
            })

    combined = pd.DataFrame(results)
    print(f"\nTotal judgments matched to at least one domain: {len(combined)}")

    audit_path = os.path.join(DATA_FINAL, "retrieval_audit_all_matches.csv")
    combined.drop(columns=["text"]).to_csv(audit_path, index=False)
    print(f"Audit file (no full text, for review) -> {audit_path}")

    for domain in ["Financial Fraud", "Corruption", "Digital Financial Fraud"]:
        # Exact token match, not substring - "Financial Fraud" is a literal
        # substring of "Digital Financial Fraud", so str.contains() would
        # wrongly pull Digital-only matches into the Financial Fraud file.
        domain_df = combined[
            combined["matched_domains"].apply(lambda s: domain in str(s).split("; "))
        ]
        out_path = os.path.join(DATA_FINAL, f"{domain.lower().replace(' ', '_')}_corpus.csv")
        domain_df.to_csv(out_path, index=False)
        print(f"{domain}: {len(domain_df)} judgments -> {out_path}")


if __name__ == "__main__":
    main()
