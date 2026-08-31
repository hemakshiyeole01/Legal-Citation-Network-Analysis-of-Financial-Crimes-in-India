# network/graph_construction (Phase 2 - Person A)

Builds one directed NetworkX graph per domain from the internal edge lists.

## Run (after network/citation_network/build_edges.py)
```
python network/graph_construction/build_graphs.py
```

## What it does
- Adds every judgment in the domain corpus as a node (even ones with zero
  citations - isolated nodes are still real data points, and matter for
  accurate density/coverage reporting)
- Adds edges from `*_edges_internal.csv` (citing -> cited)
- Each node carries `year` and `title` attributes, so later analysis
  scripts don't need to re-join back to the corpus CSVs

## Output (output/graphs/)
- `<domain>_graph.gpickle` - the NetworkX graph object (load with `pickle.load`)
- `<domain>_graph.graphml` - same graph, human-readable format, opens
  directly in Gephi if you want polished figures for the report
- `graph_summary.csv` - nodes/edges/density/isolated-node% per domain,
  side by side - your first real cross-domain comparison table

## Expect a high isolated-node percentage
Given the modest internal-citation resolution rate from Phase 1, most
nodes will have zero in/out edges within their own domain. This is
expected, not a bug - report it honestly as a limitation (most citation
activity in this corpus points outside the domain-filtered subset, or to
cases outside the dataset entirely) rather than a flaw in graph
construction itself.

## Next step (Phase 3)
`network/network_analysis/` computes centrality/PageRank on these graphs.
Isolated nodes will trivially score 0 on everything - that's correct
behavior, not something to filter out beforehand.
