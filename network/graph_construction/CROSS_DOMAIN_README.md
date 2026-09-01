# network/graph_construction - Cross-Domain Graph

Companion to `build_graphs.py`. That script only includes INTERNAL edges
(same domain both sides), so cross-domain citations - e.g. a Digital
Fraud case citing a Financial Fraud case - never appear anywhere. This
script builds a combined graph across all 3 domains that includes both
INTERNAL and CROSS_DOMAIN edges, plus a domain-to-domain citation matrix.

## Run (after network/citation_network/build_edges.py)
```
python network/graph_construction/build_cross_domain_graph.py
```

## Output
- `output/graphs/combined_cross_domain_graph.gpickle` / `.graphml` - one
  graph, all 3 domains, nodes tagged with their domain(s)
- `output/tables/domain_citation_matrix.csv` - rows = citing domain,
  columns = cited domain. Directly answers "which domain cites which
  domain, and how much" - this is what confirms/quantifies findings like
  "Digital Fraud cites Financial Fraud far more than it cites itself".

## Handling judgments that match multiple domains
A judgment can genuinely belong to more than one domain (e.g. a case
involving both cheating and bribery matches Financial Fraud AND
Corruption). Nodes are tagged with all applicable domains
(semicolon-joined, e.g. "Corruption; Financial Fraud"), and the citation
matrix counts such a judgment toward every domain it belongs to, rather
than picking just one arbitrarily.
