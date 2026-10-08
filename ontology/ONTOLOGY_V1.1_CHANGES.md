# Ontology v1.1 - Adding Violent Crime/Homicide and Organized Crime/Extortion

Per the guide's request: 2 domains related to financial crime but not
financial in category - crimes that are financially *motivated* rather
than financially *classified*.

## What changed

**`ontology/financial_crime_ontology/legal_crime_ontology_v1_1.csv`**
- All 15 v1.0 rows carried over unchanged (v1.0 file itself is left in
  place as the frozen historical record)
- New `required_context` column added to every row
- 6 new rows across 2 new domains:
  - **Violent Crime / Homicide**: Contract Killing, Corruption-linked
    Murder, Blackmail-linked Murder (Money/Business-Dispute Murder
    deliberately held back - see "Held back" below)
  - **Organized Crime / Extortion**: Extortion, Kidnapping for Ransom,
    Organised Crime / Syndicate

**`ontology/mappings/context_groups.csv`** (new file)
Reusable marker-term lists, referenced by name from the ontology's
`required_context` column: `financial_context`, `digital_context`
(both carried over from the old hardcoded Digital Fraud logic),
`contract_killing_context`, `corruption_linked_murder_context`,
`blackmail_context`, `organized_crime_financial_context`.

**`retrieve_domains.py` refactored** (two structural changes, not just new rows):
1. Domain list is now read from the ontology's `crime_category` column
   instead of a hardcoded `["Financial Fraud", "Corruption", "Digital
   Financial Fraud"]` list. Adding a domain in future only means adding
   ontology rows - no script changes needed.
2. The Digital-Fraud-only "financial + digital context" check is now a
   generic `required_context` column resolved against
   `context_groups.csv`. Any row can require 1+ context groups (joined
   with `+` for AND logic), or none at all.

## Legal basis (verified against primary/semi-primary sources)
- IPC 302 (murder) <-> BNS 103(1); IPC 307 (attempt to murder) <-> BNS 109
  - confirmed directly: BNS 109 explicitly corresponds to IPC 307
- IPC 383-389 (extortion) <-> BNS 308 (not 1:1 - BNS 308 has graded
  sub-clauses for fear of injury/death/false accusation)
- IPC 364A (kidnapping for ransom) <-> BNS 140(2) - Supreme Court has held
  this section isn't attracted without an actual ransom demand, a useful
  natural substantiveness test
- MCOCA Section 3 = punishment for organised crime (primary), Section 4 =
  possessing unaccountable wealth on behalf of a syndicate member
  (supporting) - confirmed directly
- BNS 111/112 create a central organised-crime offence for the first time
  (in force 1 July 2024) - prior prosecutions relied on state Acts
  (MCOCA, Gangster Acts), so pre-2024 judgments will cite those, not BNS

## Held back: Money/Business-Dispute Murder
Per discussion, this subcategory is deliberately NOT included yet. It has
no clean statutory anchor (murder alone isn't "financial"), and its
motive markers (business rivalry, monetary dispute, loan recovery) are
far more generic than the other 2 Homicide subcategories - high risk of
flooding the domain with ordinary murders that happen to mention money
in passing. Revisit once you've seen how Contract Killing and
Corruption-linked Murder perform on the full corpus.

## Bugs found and fixed while building v1.1 (tested against real data before shipping)

**1. IPC 120B (conspiracy) wrongly included as a "murder section."**
Conspiracy is charged alongside almost any criminal case, not just
murder - including it meant ordinary cases could rack up "murder-family"
hits without any real murder charge. Removed from all 3 Homicide rows'
`section_for_retrieval`.

**2. "prevention of corruption act" as a Corruption-linked Murder marker
was circular.** It's literally the Corruption domain's own Act name, so
any ordinary PCA bribery case with an incidental 120B mention would
satisfy both the (buggy) murder-section check and this marker
simultaneously. Confirmed on real data: 6 unrelated bribery cases (Hazari
Lal, Meet Singh, R.K. Garg, etc.) were wrongly tagged as "Corruption-linked
Murder" before this fix; 0 after.

**3. Bigger, pre-existing bug surfaced by the new domains: the `s\.?`
section-pattern alternative had no word-boundary requirement before it.**
It matched the embedded "s." inside unrelated text like "Crl. A. Nos.
383/78" (a case/appeal docket number) or "Rs. 420", misreading them as
section citations. This wasn't new - it silently affected the original 3
domains too (Financial Fraud dropped 16->15, Digital Fraud 2->1 on the
same test corpus once fixed) - it just happened not to collide visibly
until Extortion's section range (383-389) overlapped with ordinary
1970s-80s appeal-number ranges. Fixed by requiring a word boundary before
the whole section-pattern alternation, so "S. 420" still matches but
"Nos. 420" and "Rs. 420" don't. **Re-run retrieve_domains.py even if
you're not touching the new domains - your existing 3 domain corpora
need regenerating with this fix.**

## Validated on real 1980-81 test data (799 judgments)
| Domain | Count | Notes |
|---|---|---|
| Financial Fraud | 15 | was 16 before the word-boundary fix |
| Corruption | 10 | unaffected |
| Digital Financial Fraud | 1 | was 2 before the word-boundary fix |
| Violent Crime / Homicide | 1 | the 1 remaining is a known outlier (see below) |
| Organized Crime / Extortion | 7 | was 10 before removing docket-number false positives |

**Known remaining limitation:** Bachan Singh v. State of Punjab (the
death-penalty constitutionality case) still matches Contract Killing with
231 hits and Organised Crime/Syndicate with several. This is one of the
longest, most-cited judgments in Indian legal history, discussing murder
extensively for constitutional reasons unrelated to any actual contract
killing. Same class of outlier as S.P. Gupta's false positives found
earlier in this project (Phase 0) - a single huge landmark document
colliding with keyword matching, not a systematic flaw. Catch it in the
manual spot-check (Step 10), don't try to eliminate it in code.
