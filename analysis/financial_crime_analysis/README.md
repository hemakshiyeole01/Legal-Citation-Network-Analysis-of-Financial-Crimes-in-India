# analysis/financial_crime_analysis (Phase 6)

```
python analysis/financial_crime_analysis/compare_domains.py
```
Needs Phases 3, 4 and 5 to have run.

| Output | Contents |
|---|---|
| `insularity_by_domain.csv` | Own-domain citation rate vs chance, with counts behind it |
| `domain_comparison.csv` | Everything side by side, one row per domain |
| `output/visualizations/domain_comparison.png` | Average citations per case; own-domain rate vs chance |
| `output/reports/results_summary.md` | Auto-generated draft of the results section |

## The new measure: own-domain citation rate vs chance
For every citation a domain's case makes to another case inside the five
domains, the script asks: if it had picked an older case at random, how likely
was it to land in the same domain? Summed, that is the EXPECTED number of
own-domain citations. Observed / expected:

- 1.0 = no preference for its own domain
- above 1 = cites its own domain more than chance
- below 1 = cites the other domains more than chance

"Older" and "available" use the citing case's year, so a domain is not
penalised for cases that did not exist yet. Intervals are a bootstrap over
citing cases (a case's citations are not independent of each other).

**When no ratio is reported:** if fewer than 5 own-domain citations were
expected by chance (`MIN_EXPECTED_OWN` in the script), the ratio is left blank
(`n/a`). Observing 0 when chance predicts 0.3 says nothing, and a bootstrap
interval of 0-0 would look falsely certain. The counts are still in
`insularity_by_domain.csv` (`expected_too_small = True`).

**Small domains** (under 100 cases, `SMALL_DOMAIN_CASES`) are described in the
report but not ranked or tested.

## About results_summary.md
Every number is computed, and the sentences are rule-generated from those
numbers. It is a DRAFT for the results section: read each sentence against the
tables, edit the wording, and add the interpretation only you can supply
(legal reasons for the patterns). It deliberately makes no causal claims.
