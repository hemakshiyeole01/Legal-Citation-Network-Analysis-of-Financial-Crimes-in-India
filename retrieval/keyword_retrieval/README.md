# retrieval/keyword_retrieval

Implements Steps 8-9: classifies judgments into the 3 domains using the
frozen ontology (Stage 1 high-recall matching + Stage 2 precision filters).

## Run (after preprocessing/cleaning/clean_text.py)
```
python retrieval/keyword_retrieval/retrieve_domains.py
```

## How it works
- **Stage 1**: matches each judgment against every ontology subcategory's
  section numbers (e.g. "Section 420") and keywords.
- **Stage 2 filters**:
  - A signal must appear **2+ times** to count (filters out passing
    mentions vs. substantive discussion).
  - **Digital Financial Fraud** additionally requires BOTH a financial
    context term (money, payment, transaction, etc.) AND a genuine
    digital/cyber context term (computer, internet, online, IT Act, etc.)
    to co-occur. Without this, ordinary IPC 420 cheating cases (used as a
    supporting signal per the ontology) would get mistagged as digital
    fraud - including judgments from before the IT Act existed (pre-2000).
    Verified against real 1980-81 data: false positives dropped from 16
    to 2 after adding this check.

## Output (data/final/)
- `financial_fraud_corpus.csv`
- `corruption_corpus.csv`
- `digital_financial_fraud_corpus.csv`
- `retrieval_audit_all_matches.csv` - all matches with subcategory + hit
  counts, no full text, for manual review (Step 10)

## Known limitation
Keyword matching can occasionally hit rhetorical/metaphorical language
(e.g. "feed into a judicial computer" matching "computer"). This is
expected and exactly what the manual spot-check step is for - don't
try to eliminate every edge case in code.
