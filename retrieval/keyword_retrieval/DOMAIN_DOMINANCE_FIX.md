# Domain dominance fix (found via the 5-domain, 250-row manual spot-check)

## The bug
`matched_domains.add(rule["crime_category"])` ran the instant ANY single
subcategory cleared the Stage 2 threshold - with zero comparison against
how strong other domains' signals were in the same document. A murder
case mentioning "forged" 3 times (clearing Forgery & Falsification's
threshold) got filed under Financial Fraud even when Murder cleared 10
hits in the same judgment.

This was always present in the matching logic, going back to the
original 3-domain version - it just wasn't very visible with fewer
domains and narrower keyword coverage. Expanding to 5 domains multiplied
the keyword/section surface area enough that incidental cross-domain
hits became a frequent, real problem rather than a rare edge case.

## How it was found
Manual spot-check of 250 rows (50/domain) across all 5 domains.
Precision by domain: Corruption 34/50, Financial Fraud 20/50, Digital
Financial Fraud 19/50 (worst - barely above chance), Organized Crime
27/50, Violent Crime/Homicide 41/50 (best - Murder/Attempt to Murder are
unambiguous, low-overlap keywords). The labeling methodology itself
diagnosed the root cause: every "No" traced back to the assigned
domain's own subcategory hits being far outweighed by a different
domain's hits in the same document.

## The fix
For each judgment, hit totals are now aggregated per domain (summing
across all of that domain's passing subcategories), and a domain is
dropped from the judgment's assignment if any other domain present is
at least 2x stronger. The 2x threshold isn't arbitrary - it's the exact
rule used to manually label the spot-check, so this encodes a
human-validated judgment call rather than a made-up cutoff.

Genuinely comparable multi-domain cases (e.g. a case substantively about
both corruption and organized crime) are preserved - neither domain
outweighs the other by 2x, so both are kept. Only lopsided, incidental
secondary matches get dropped.

## New audit columns
`retrieval_audit_all_matches.csv` now includes:
- `domain_hit_totals` - every domain's aggregate hit count for that
  judgment, sorted strongest first (e.g. "Violent Crime / Homicide:229;
  Financial Fraud:3")
- `suppressed_domains` - domains that had a passing subcategory but were
  dropped by the dominance rule

This is exactly the information you had to manually reconstruct by
mapping subcategories to domains and summing by hand for the spot-check
- it's now computed automatically, so future spot-checks (or anyone
auditing a specific judgment's classification) don't need to redo that
work.

## Validated on real 1980-81 test data
- Bachan Singh v. State of Punjab (the known huge-outlier document,
  flagged since Phase 0) is now correctly resolved: Violent Crime /
  Homicide:229 kept, Financial Fraud:3 / Digital Financial Fraud:2 /
  Organized Crime:2 all correctly suppressed. This was an "accepted
  limitation" noted repeatedly throughout this project - the dominance
  fix resolves it as a side effect, with no special-casing needed.
- 6 genuine multi-domain cases survived on the test set (e.g. V.C.
  Shukla: Organized Crime 24 / Financial Fraud 20 / Homicide 20 - a
  real case spanning political corruption and financial dealings) -
  confirming the fix doesn't over-correct into forcing single-domain
  assignment where multi-domain membership is actually warranted.

## What to do
Re-run the full pipeline from retrieval onward - domain corpus
membership changes for all 5 domains (fewer incidental secondary
matches), so everything downstream (citations, edges, graphs) needs
regenerating.
