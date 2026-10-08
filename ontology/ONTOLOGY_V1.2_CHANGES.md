# Ontology v1.2 - Domains 4 and 5 made fully general

v1.1 scoped Violent Crime/Homicide and Organized Crime/Extortion to
financially-motivated subsets only (contract killing, corruption-linked
murder, etc.), reasoning that the guide's example ("murder due to
corruption") implied a motive filter. On reflection: the guide didn't
actually give that example - it was added during scoping to keep
consistency with the project title. Since the guide's actual ask was
just "2 more domains" with no financial requirement, v1.2 reverts the
filter and treats domains 4 and 5 as general, standard crime categories.

## Reframing
Domains 1-3 (Financial Fraud, Corruption, Digital Financial Fraud)
remain the core comparative thesis: citation density across financial
law of different ages. Domains 4-5 (Homicide, Organized Crime/Extortion)
now serve as a **comparison baseline**: do financial-crime citation
networks behave differently from ordinary criminal-law citation
networks at all? That's a legitimate, arguably stronger research
question than forcing everything under a financial-crime umbrella.

**Action needed:** update the project title/framing to reflect this -
"Legal Citation Network Analysis of Financial Crimes in India" no longer
precisely describes 2 of 5 domains. Either adjust the title or make the
comparison-baseline framing explicit in your synopsis/report methodology
section.

## What changed from v1.1
- `required_context` column is now blank for all 6 new-domain rows (no
  more financial/digital-style gating)
- Subcategories rebuilt as standard legal categories instead of
  motive-specific ones:
  - **Violent Crime / Homicide**: Murder (IPC 302/BNS 103), Attempt to
    Murder (IPC 307/BNS 109), Culpable Homicide not amounting to Murder
    (IPC 299,304/BNS 100,105)
  - **Organized Crime / Extortion**: unchanged from v1.1 (Extortion,
    Kidnapping for Ransom, Organised Crime/Syndicate) - these already had
    no `required_context` gate except Organised Crime/Syndicate, which
    now also drops its financial-marker requirement
- IPC 120B (conspiracy) still deliberately excluded from Murder's
  countable sections - that fix from v1.1 remains valid regardless of
  the motive-filter decision; conspiracy alone was never a reliable
  murder signal

## Validated on real 1980-81 test data (799 judgments)
| Domain | Count | % of test corpus |
|---|---|---|
| Financial Fraud | 15 | 1.9% |
| Corruption | 10 | 1.3% |
| Digital Financial Fraud | 1 | 0.1% |
| Organized Crime / Extortion | 27 | 3.4% |
| Violent Crime / Homicide | 59 | 7.4% |

**The scale difference is real and expected, not a bug.** Spot-checked a
random sample of 10 Homicide matches - 9 were genuine, substantively-
discussed murder appeals (clean "State vs accused" case pattern, hit
counts 2-12). The one exception (S.P. Gupta) is the same known
huge-outlier-document false positive flagged earlier in this project
(Phase 0) - not a new issue. At full 26,688-judgment corpus scale,
expect Homicide to come in several times larger than Financial Fraud -
report this honestly as a finding about relative litigation volume, not
something to filter away.
