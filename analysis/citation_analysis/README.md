# analysis/citation_analysis (Phase 5)

```
python analysis/citation_analysis/analyze_citations.py
```

| Output | Contents |
|---|---|
| `most_cited_overall.csv` | Top 20 judgments by citations from all five domains |
| `most_cited_by_domain.csv` | Top 10 per domain by citations from the same domain |
| `citation_trend_by_decade.csv` | Per decade: cases decided, citations those cases make, per case |
| `average_citations_per_case.csv` | Mean citations received per case with 95% bootstrap intervals; median citation lag with interval |
| `output/visualizations/citation_intensity_by_decade.png` | Citations made per case over time |

**Most-cited vs most influential:** this phase ranks by raw citation count;
Phase 4 ranks by PageRank. They can disagree, which is informative.

**Reading the trend chart:** each point is one decade's cases. Decades with
fewer than 20 cases are not plotted, but points built on 20-100 cases are
still noisy - the intervals in `average_citations_per_case.csv` show how much.
Do not describe a zigzag between neighbouring decades as a trend.

**Intervals:** percentile bootstrap over cases (2,000 resamples, seed 42), so
the numbers are reproducible. A domain with no citations shows an interval of
zero width; that means "none observed", not "certainly none".
