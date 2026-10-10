# analysis/case_analysis (Phase 4)

```
python analysis/case_analysis/analyze_cases.py [--top 10]
```

| Output | Contents |
|---|---|
| `top_cases_by_domain.csv` | Top-N cases per domain |
| `domain_distribution_by_decade.csv` | Cases per decade, and as a % of ALL Supreme Court judgments that decade |
| `domain_age_profile.csv` | First / median / last year, share before 1980, 1980-99, 2000 onward |
| `output/visualizations/domain_distribution_by_decade.png` | Both views as a chart |

**Ranking rule (top cases):** PageRank within the domain's own graph, ties
broken by citations received from all five domains. Both counts are in the
table (`citations_same_domain`, `citations_from_outside_this_domain`,
`citations_from_all_five_domains`) so a ranking can be questioned. Only cases
cited at least once by another case in the study are eligible. A domain with
no internal citations (e.g. Digital Financial Fraud) will list only cases
cited from other domains - read `citations_same_domain` before calling any of
those "influential in the domain".

**Reading the decade chart:** use the right-hand panel (share of all
judgments) to judge growth - the left panel mixes "domain grew" with "the
Court decided more cases". The 2020s cover only 2020-2025 (six years), so the
left panel dips there by construction.
