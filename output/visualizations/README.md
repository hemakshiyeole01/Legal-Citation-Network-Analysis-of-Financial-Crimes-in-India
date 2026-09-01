# output/visualizations

Generates interactive HTML network visualizations - open directly in any
browser, no server or technical setup needed. Good for showing your
guide/professor how the graphs actually look.

## Run (after all network/ scripts)
```
python output/visualizations/visualize_graphs.py
```

## Output (output/visualizations/)
- `financial_fraud_network.html`
- `corruption_network.html`
- `digital_financial_fraud_network.html`
- `combined_cross_domain_network.html` - all 3 domains together, nodes
  colored by domain

## How to show your professor
Just double-click the `.html` file - opens in her default browser. She
can drag nodes around, zoom, and hover over any node to see the case
title, year, and how many citation links it has. No installation, no
Python, no explanation needed beyond "click and drag to explore."

## Note on what's shown
Only judgments with at least one citation link are shown - given the
modest internal-resolution rate, most nodes are isolated (0 edges) and
would just clutter the view as disconnected dots. Full isolated-node
counts are already reported honestly in `output/graphs/graph_summary.csv`
- this visualization is for showing the actual network structure, not a
complete inventory of every judgment.

## For your report (static images)
The `.graphml` files in `output/graphs/` open directly in **Gephi**
(free, gephi.org) if you want a polished, publication-style static image
for your synopsis/report rather than an interactive HTML file.
