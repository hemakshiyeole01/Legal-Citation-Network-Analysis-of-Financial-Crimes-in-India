"""
Stage: retrieval/keyword_retrieval

Implements Steps 8-9 of the project checklist:
  Stage 1 (high recall): match judgments against ontology keywords + section
      numbers -> broad candidate pool per subcategory
  Stage 2 (precision filter): keep only matches where the signal appears
      more than once (proxy for "substantively discussed" vs "merely cited
      in passing", per the ontology's inclusion/exclusion rules), and for
      any subcategory with a required_context group, require the
      co-occurring context term(s) (per that row's exclusion rule).

v1.1 change: the domain list and the Digital-Fraud-only context logic used
to be hardcoded here. Both are now generic: domains are read from the
ontology's crime_category column, and required_context is a column on
each ontology row (group name(s), joined with "+" for AND logic) resolved
against ontology/mappings/context_groups.csv. This is what let Violent
Crime/Homicide and Organized Crime/Extortion get added without touching
this matching logic - only the ontology CSV changed.

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

from config.paths import DATA_PROCESSED, DATA_FINAL, ONTOLOGY_PATH, CONTEXT_GROUPS_PATH

INPUT_FILE = os.path.join(DATA_PROCESSED, "all_judgments_cleaned.csv")

# Signal must appear at least this many times to count as "substantive"
# rather than a passing/incidental mention (Stage 2 precision rule).
MIN_OCCURRENCES_FOR_INCLUSION = 2

# Act-name signal phrases, keyed by a short tag. Used to gate section-number
# matches: bare section numbers (e.g. PMLA's "3","4","5","8", PCA's
# "7","8","9", or MCOCA's "3","4") are generic digits that appear in
# countless unrelated Acts. A section match only counts if the Act it
# belongs to is actually named somewhere in the document.
ACT_SIGNAL_PHRASES = {
    "ipc_bns": ["indian penal code", " ipc", "bharatiya nyaya sanhita", " bns"],
    "companies_act": ["companies act"],
    "pmla": ["prevention of money laundering act", "pmla", "money laundering act"],
    "cgst": ["cgst act", "goods and services tax act", "gst act", "central goods and services tax"],
    "pca": ["prevention of corruption act", " pca "],
    "it_act": ["information technology act", "it act"],
    "mcoca_gangster": [
        "maharashtra control of organised crime act", "mcoca",
        "control of organised crime", "gangsters act",
        "organised crime syndicate", "petty organised crime",
    ],
}


def compile_terms(terms, allow_suffix: bool):
    r"""Compiles a list of terms/phrases into ONE word-boundary-aware regex.

    Why not plain `term in text`: raw substring matching fires inside
    unrelated words. Measured on real 1980-81 judgments (before the IT Act
    existed): "online" substring-matched 24 of 799 judgments (strict match:
    0), "sms" matched 18 (inside "mechanisms"; strict: 0), and the Act-name
    gate "it act" matched 18 (inside "until it acts", "it acted"; strict
    Act-name match: 0). Those false passes were enough to push pre-2000
    judgments through the Digital Financial Fraud gates.

    - (?<!\w) before: the term can't start mid-word ("observer" != "server")
    - (?!\w) after: the term can't run on into a longer word
      ("it acts" != "it act")
    - allow_suffix (context terms only): tolerate plural/inflection so
      "transactions"/"payments" still match "transaction"/"payment".
      Act names pass allow_suffix=False - they're proper names.
    - Terms ending in punctuation (e.g. "rs.") get no trailing check so
      "Rs.500" still matches."""
    word_end, other_end = [], []
    for t in terms:
        t = t.strip().lower()
        if not t:
            continue
        (word_end if t[-1].isalnum() else other_end).append(re.escape(t))

    parts = []
    if word_end:
        suffix = r"(?:s|es|ed|ing)?" if allow_suffix else ""
        parts.append(r"(?:" + "|".join(word_end) + r")" + suffix + r"(?!\w)")
    if other_end:
        parts.append(r"(?:" + "|".join(other_end) + r")")
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")")


COMPILED_ACT_PATTERNS = {
    tag: compile_terms(phrases, allow_suffix=False)
    for tag, phrases in ACT_SIGNAL_PHRASES.items()
}


def load_context_groups():
    """group_name -> compiled word-boundary regex, from
    ontology/mappings/context_groups.csv."""
    df = pd.read_csv(CONTEXT_GROUPS_PATH)
    groups = {}
    for _, row in df.iterrows():
        terms = [t.strip().lower() for t in str(row["terms"]).split(",") if t.strip()]
        groups[row["group_name"].strip()] = compile_terms(terms, allow_suffix=True)
    return groups


def parse_required_context(field) -> list:
    """Ontology's required_context cell -> list of group names that must
    ALL be present (AND logic). Blank/NaN means no extra context gate."""
    if pd.isna(field) or not str(field).strip():
        return []
    return [g.strip() for g in str(field).split("+") if g.strip()]


def has_required_context(text_lower: str, group_names: list, context_groups: dict) -> bool:
    """True if every required group has at least one of its terms present
    (as a whole word/phrase - see compile_terms)."""
    for group_name in group_names:
        if not context_groups[group_name].search(text_lower):
            return False
    return True


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
    if "mcoca" in act_lower or "gangster" in act_lower or "organised crime" in act_lower:
        tags.append("mcoca_gangster")
    return tags


def has_act_context(text_lower: str, act_tags, tag_cache: dict) -> bool:
    """True if the document names at least one of the relevant Acts (whole
    phrase, not substring). If no tags were detected for this row (unmapped
    act), don't gate - fall back to keyword-only matching for that row.

    tag_cache is per-document: many ontology rows share an Act tag (12 rows
    use ipc_bns), so each Act is searched for once per judgment, not once
    per row."""
    if not act_tags:
        return True
    for tag in act_tags:
        if tag not in tag_cache:
            tag_cache[tag] = bool(COMPILED_ACT_PATTERNS[tag].search(text_lower))
        if tag_cache[tag]:
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
    r"""Builds regex patterns matching 'Section 420', 'Sec. 420', 'S. 420', 'u/s 420', etc.
    The leading \b is required: without it, the bare 's\.?' alternative
    matches the 's.' embedded inside unrelated text like 'Crl. A. Nos.
    383/78' (a case/appeal docket number) or 'Rs. 420', misreading them as
    section citations. \b forces 's' to be its own token, so legitimate
    'S. 420' style citations still match while 'Nos. 383' and 'Rs. 420' don't."""
    patterns = []
    for token in tokens:
        escaped = re.escape(token)
        pattern = re.compile(
            rf"\b(?:section|sec\.?|s\.?|u/s)\s*{escaped}\b", re.IGNORECASE
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


def domain_to_filename(domain: str) -> str:
    """'Organized Crime / Extortion' -> 'organized_crime_extortion'"""
    return domain.lower().replace(" / ", "_").replace(" ", "_")


def main():
    print("Loading ontology...")
    ontology = load_ontology()
    context_groups = load_context_groups()

    domains = sorted(ontology["crime_category"].unique().tolist())
    print(f"Domains in ontology: {domains}")

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
        required_context = parse_required_context(row.get("required_context"))
        unknown = [g for g in required_context if g not in context_groups]
        if unknown:
            raise ValueError(
                f"Ontology row '{row['subcategory']}' requires unknown context "
                f"group(s) {unknown} - not in context_groups.csv"
            )
        ontology_rules.append({
            "crime_category": row["crime_category"],
            "subcategory": row["subcategory"],
            "section_patterns": section_patterns,
            "keywords": keywords,
            "act_tags": act_tags,
            "required_context": required_context,
        })

    results = []

    # A domain is dropped from a judgment's assignment if some OTHER domain
    # present in the same judgment has a total hit count at least this many
    # times higher. Without this, a domain was being assigned the instant
    # ANY one of its subcategories cleared the Stage 2 threshold, with zero
    # regard for how dominant a different domain's signal was in the same
    # document - e.g. a murder case mentioning "forged" 3 times (passing
    # Forgery & Falsification's threshold) got filed under Financial Fraud
    # even when Murder cleared 10 hits in the same judgment. Confirmed via
    # manual spot-check (250 rows, 5 domains): this was a real, frequent
    # problem, not an edge case - worst in Digital Financial Fraud (19
    # Yes / 21 No). The 2x threshold matches the rule used to manually
    # label that spot-check, so this encodes a human-validated judgment
    # call rather than an arbitrary cutoff.
    DOMINANCE_RATIO = 2.0

    for _, jrow in tqdm(judgments.iterrows(), total=len(judgments), desc="Classifying"):
        text_lower = jrow["text"].lower()
        passing_rules = []  # (crime_category, subcategory, total)
        tag_cache = {}  # Act tag -> named in this document? (see has_act_context)

        for rule in ontology_rules:
            act_context_ok = has_act_context(text_lower, rule["act_tags"], tag_cache)
            total, signals = count_matches(
                text_lower, rule["section_patterns"], rule["keywords"], act_context_ok
            )

            if total < MIN_OCCURRENCES_FOR_INCLUSION:
                continue  # Stage 2: not substantive enough

            # Generic context gate (replaces the old Digital-Fraud-only
            # hardcoded check). E.g. Violent Crime/Homicide rows require a
            # motive marker so plain murder cases don't flood the domain;
            # Digital Fraud rows require financial+digital co-occurrence.
            if rule["required_context"]:
                if not has_required_context(text_lower, rule["required_context"], context_groups):
                    continue

            passing_rules.append((rule["crime_category"], rule["subcategory"], total))

        if not passing_rules:
            continue

        # Aggregate hit totals per domain (a domain can have multiple
        # passing subcategories - sum them for a fair comparison).
        domain_totals = {}
        for crime_category, _, total in passing_rules:
            domain_totals[crime_category] = domain_totals.get(crime_category, 0) + total

        max_total = max(domain_totals.values())

        # Keep a domain unless some other domain in this judgment is at
        # least DOMINANCE_RATIO times stronger. The dominant domain(s)
        # always pass this trivially; genuinely comparable multi-domain
        # cases (e.g. a real corruption-linked murder) also both pass,
        # since neither outweighs the other by 2x - only truly incidental,
        # lopsided secondary matches get dropped.
        kept_domains = {
            d for d, t in domain_totals.items() if t * DOMINANCE_RATIO >= max_total
        }
        suppressed_domains = set(domain_totals) - kept_domains

        matched_subcats = [
            f"{subcat} [{total} hits]" for cc, subcat, total in passing_rules
        ]
        domain_totals_str = "; ".join(
            f"{d}:{t}" for d, t in sorted(domain_totals.items(), key=lambda x: -x[1])
        )

        results.append({
            "file_name": jrow["file_name"],
            "year": jrow["year"],
            "char_count": jrow["char_count"],
            "matched_domains": "; ".join(sorted(kept_domains)),
            "domain_hit_totals": domain_totals_str,
            "suppressed_domains": "; ".join(sorted(suppressed_domains)) if suppressed_domains else "",
            "matched_subcategories": "; ".join(matched_subcats),
            "text": jrow["text"],
        })

    combined = pd.DataFrame(results)
    print(f"\nTotal judgments matched to at least one domain: {len(combined)}")

    audit_path = os.path.join(DATA_FINAL, "retrieval_audit_all_matches.csv")
    combined.drop(columns=["text"]).to_csv(audit_path, index=False)
    print(f"Audit file (no full text, for review) -> {audit_path}")

    for domain in domains:
        # Exact token match, not substring - "Financial Fraud" is a literal
        # substring of "Digital Financial Fraud", so str.contains() would
        # wrongly pull Digital-only matches into the Financial Fraud file.
        domain_df = combined[
            combined["matched_domains"].apply(lambda s: domain in str(s).split("; "))
        ]
        out_path = os.path.join(DATA_FINAL, f"{domain_to_filename(domain)}_corpus.csv")
        domain_df.to_csv(out_path, index=False)
        print(f"{domain}: {len(domain_df)} judgments -> {out_path}")


if __name__ == "__main__":
    main()
