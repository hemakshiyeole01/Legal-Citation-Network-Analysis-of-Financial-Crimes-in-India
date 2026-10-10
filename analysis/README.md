# analysis/ - Phases 4, 5, 6 (Person A)

Run in this order, after the network stage has been rebuilt:

```
python network/network_analysis/analyze_networks.py            # Phase 3 (writes node_metrics.csv etc.)
python analysis/case_analysis/analyze_cases.py                 # Phase 4
python analysis/citation_analysis/analyze_citations.py         # Phase 5
python analysis/financial_crime_analysis/compare_domains.py    # Phase 6 (needs 4 and 5 first)
```
Everything lands in `output/tables/`, `output/visualizations/` and
`output/reports/results_summary.md`. Re-run all four after ANY change to the
domain corpora or graphs - later phases read earlier phases' tables.

Scope decision (applies to all three): influence and citation counts use only
citations BETWEEN the judgments in the five domain corpora. Citations from the
other ~22,000 judgments in the dataset are not counted.
