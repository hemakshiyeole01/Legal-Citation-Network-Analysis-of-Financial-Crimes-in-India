# Word-boundary fix for the Act-name and context gates

Found via the second 5-domain spot-check (100 rows, 20/domain, run after the
dominance fix). Four domains came back with 0 "No" labels out of 80 rows.
Digital Financial Fraud had 6 "No"s - all judgments from 1950-1987, all tagged
only with the two weak cyber subcategories, with identical hit counts on both
(i.e. the same bare section numbers 43 / 66 being counted twice).

## Root cause
Two gates used raw substring checks (`term in text`):

1. Act-name gate: the IT Act was detected by the substring "it act". That
   matches "until it acts", "it acted in the sound...", and "profit actually",
   "benefit actually", "credit actually" (very common in tax cases). Once that
   gate passed, bare section numbers 43 and 66 - from ANY unrelated Act (e.g.
   Income-tax Act s.66, the High Court reference provision) - were counted as
   IT Act hits.
2. Digital-context gate: substring terms fired inside unrelated words.
   Measured on 799 real 1980-81 judgments (pre-internet):
   | term   | substring matches | whole-word matches |
   |--------|-------------------|--------------------|
   | online | 24                | 0                  |
   | sms    | 18 (mechanisms)   | 0                  |
   | server | 6 (observer)      | 0                  |
   | otp    | 3                 | 0                  |
   And "it act" itself was also in the digital list.

## Fix (retrieval/keyword_retrieval/retrieve_domains.py)
- `compile_terms()` builds whole-word/phrase regexes: `(?<!\w)` before,
  `(?!\w)` after. Context terms tolerate plural/inflection (payments,
  transactions, computers). Act names do not (they are proper names).
- Act presence is checked once per Act per judgment (cached), not once per
  ontology row.
- A typo'd group name in the ontology's `required_context` now raises an error
  instead of silently disabling that row.
- `context_groups.csv`: removed the ambiguous "it act" from digital_context
  (the Act-name gate already covers it).

## Verification
- 16/16 controlled string checks: false positives ("it acts", "mechanisms",
  "observer") rejected; genuine text ("Information Technology Act, 2000",
  "online banking", "SMS", "Rs.500", "payments") still matches.
- Constructed 1950s tax-style passage: old gates tagged it Cyber-enabled
  Financial Offence; new gates do not.
- 799-judgment regression run, old vs new gates: all other documents
  keep identical domain assignment; one extra match (Niranjan Singh, a
  murder-bail case - "IPC" sat at the start of a wrapped line and the old
  gate required a leading space).

## Limits - what this does NOT prove
- The test judgments here are 1980-81. The failing rows were 1950-1968, which
  are not in the test set, so the six original "No"s were not reproduced
  directly. The full-corpus re-run is the real test.
- Known residual weakness: rows that mix IT Act sections with IPC/BNS
  (Digital/Payment Fraud) are gated by the IPC name, so bare "section 43(1)" /
  "66(1)" from other Acts can still count when a judgment mentions the IPC.
  Bachan Singh shows this (also a "judicial computer" metaphor); it is
  suppressed by the dominance rule, but a pre-2000 judgment with no stronger
  domain could still carry it. If pre-2000 Digital rows survive the re-run,
  the options are a year gate (Digital rows require year >= 2000, the IT
  Act's commencement) or splitting the mixed rows into IT-Act-only and
  IPC-only rows.
