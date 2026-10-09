# network/network_analysis (Phase 3 - Person A)

Structural and influence metrics for every domain graph plus the combined
all-domain graph.

## Run (after network/graph_construction/ has been re-run)
```
python network/network_analysis/analyze_networks.py
```

## Output (output/tables/)
| File | One row per | What it answers |
|---|---|---|
| `network_metrics_by_domain.csv` | graph | size, how connected, how long the paths are, how old the cited precedent is |
| `node_metrics.csv` | case per graph | in-degree, out-degree, PageRank, ranks - feeds Phase 4 |
| `temporal_metrics.csv` | graph per snapshot year | how each network grew decade by decade (cumulative) |
| `top_case_trajectories.csv` | top case per snapshot year | how the final top-10 cases' standing developed over time |

## How to read the metrics
- **in_degree**: how many cases in the same graph cite this one.
- **pagerank**: like in-degree, but a citation from an influential case
  counts for more. A case with fewer citations can outrank one with more.
- **pagerank_x_N**: PageRank multiplied by the graph's node count, so 1.0 =
  an average case. Use this (or the ranks) to compare across domains; raw
  PageRank shrinks as a graph grows and is NOT comparable between a 42-node
  and a 2,000-node domain.
- **mean_in_degree / pct_cited_at_least_once**: size-robust measures of how
  densely a domain cites itself. Prefer these to `density` when comparing
  domains - density = edges / (nodes x (nodes-1)) falls mechanically as a
  graph gets bigger, so a 42-node domain looks "denser" than a 2,294-node one
  for no real reason.
- **avg_path_length_largest_component**: computed on the largest weakly
  connected component, treated as undirected (directed paths between random
  cases mostly don't exist in a citation graph). Exact up to 3,000 nodes,
  otherwise estimated from 300 sampled sources (`path_method` says which).
- **median_citation_lag_years**: median gap between a citing case and the
  case it cites - how old the precedent a domain leans on is.
- **edges_citing_a_newer_case**: should be 0. Anything above is a data
  anomaly (citation resolved to the wrong judgment) to look into.

## Temporal snapshots
Cumulative: the snapshot for 1990 is every case decided up to and including
1990 and the citations among them. Decade snapshots from 1960, plus the
latest year in the data.

## Limitations to state in the report
1. **Only citations from within the five domain corpora are counted.** A
   case's in-degree here excludes citations from the other ~22,000 Supreme
   Court judgments in the dataset (tax, service, civil...). It measures
   influence *within* these crime domains, not total influence.
2. **Age bias.** Older cases have had longer to be cited, so raw in-degree and
   PageRank favour them. The temporal snapshots are the check on this.
3. **Small domains.** Digital Financial Fraud has very few cases; its metrics
   rest on a handful of edges and shouldn't be over-read.
4. **Most cases are isolated** (no citation in or out within their domain).
   That is a real property of the data, reported in `pct_isolated`.
