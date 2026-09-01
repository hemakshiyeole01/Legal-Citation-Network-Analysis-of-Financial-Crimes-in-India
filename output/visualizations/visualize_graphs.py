"""
Stage: output/visualizations

Generates interactive HTML network visualizations from the built graphs -
opens directly in any browser, no technical setup needed. Good for
demoing to your guide/professor.

Run (after network/graph_construction/build_graphs.py and
build_cross_domain_graph.py):
    python output/visualizations/visualize_graphs.py
"""

import sys
import os
import pickle

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from pyvis.network import Network

from config.paths import OUTPUT_GRAPHS, OUTPUT_VISUALIZATIONS

DOMAIN_COLORS = {
    "Financial Fraud": "#4C72B0",
    "Corruption": "#DD8452",
    "Digital Financial Fraud": "#55A868",
}


def visualize_domain_graph(domain: str):
    graph_path = os.path.join(
        OUTPUT_GRAPHS, f"{domain.lower().replace(' ', '_')}_graph.gpickle"
    )
    if not os.path.exists(graph_path):
        print(f"Skipping {domain} - graph not found: {graph_path}")
        return

    with open(graph_path, "rb") as f:
        G = pickle.load(f)

    # Only show nodes with at least one citation - a full 1000+ isolated
    # dots is unreadable and not useful for a demo. Isolated-node stats
    # are already reported separately in graph_summary.csv.
    connected_nodes = [n for n in G.nodes() if G.degree(n) > 0]
    G_sub = G.subgraph(connected_nodes)

    if G_sub.number_of_nodes() == 0:
        print(f"Skipping {domain} - no connected nodes to visualize")
        return

    net = Network(height="800px", width="100%", directed=True, notebook=False)
    net.barnes_hut(gravity=-3000, spring_length=150)

    for node, attrs in G_sub.nodes(data=True):
        degree = G_sub.degree(node)
        net.add_node(
            node,
            label=attrs.get("title", node)[:40],
            title=f"{attrs.get('title', node)} ({attrs.get('year', '?')}) - {degree} citation links",
            size=15 + degree * 5,
            color=DOMAIN_COLORS.get(domain, "#888888"),
        )

    for source, target in G_sub.edges():
        net.add_edge(source, target)

    out_path = os.path.join(
        OUTPUT_VISUALIZATIONS, f"{domain.lower().replace(' ', '_')}_network.html"
    )
    net.write_html(out_path, open_browser=False, notebook=False)
    print(f"{domain}: {G_sub.number_of_nodes()} nodes, {G_sub.number_of_edges()} edges -> {out_path}")


def visualize_combined_graph():
    graph_path = os.path.join(OUTPUT_GRAPHS, "combined_cross_domain_graph.gpickle")
    if not os.path.exists(graph_path):
        print("Skipping combined graph - not found")
        return

    with open(graph_path, "rb") as f:
        G = pickle.load(f)

    connected_nodes = [n for n in G.nodes() if G.degree(n) > 0]
    G_sub = G.subgraph(connected_nodes)

    if G_sub.number_of_nodes() == 0:
        print("Skipping combined graph - no connected nodes")
        return

    net = Network(height="800px", width="100%", directed=True, notebook=False)
    net.barnes_hut(gravity=-3000, spring_length=150)

    for node, attrs in G_sub.nodes(data=True):
        degree = G_sub.degree(node)
        domains = attrs.get("domain", "")
        # If a node is in multiple domains, color by the first one listed
        primary_domain = domains.split("; ")[0] if domains else ""
        net.add_node(
            node,
            label=attrs.get("title", node)[:40],
            title=f"{attrs.get('title', node)} ({attrs.get('year', '?')}) - domain(s): {domains}",
            size=15 + degree * 5,
            color=DOMAIN_COLORS.get(primary_domain, "#888888"),
        )

    for source, target in G_sub.edges():
        net.add_edge(source, target)

    out_path = os.path.join(OUTPUT_VISUALIZATIONS, "combined_cross_domain_network.html")
    net.write_html(out_path, open_browser=False, notebook=False)
    print(f"Combined: {G_sub.number_of_nodes()} nodes, {G_sub.number_of_edges()} edges -> {out_path}")


def main():
    os.makedirs(OUTPUT_VISUALIZATIONS, exist_ok=True)

    for domain in DOMAIN_COLORS:
        visualize_domain_graph(domain)

    visualize_combined_graph()

    print("\nOpen any .html file above directly in a browser (double-click it) - no server needed.")


if __name__ == "__main__":
    main()
