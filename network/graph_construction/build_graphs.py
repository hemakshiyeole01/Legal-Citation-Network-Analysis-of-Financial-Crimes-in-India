"""
Stage: network/graph_construction (Phase 2 of Person A's track)

Builds one directed NetworkX graph per domain from the internal edge
lists (citing_file_name -> cited_file_name, same domain both sides).
Nodes get year/title attributes so later analysis (temporal, labeling)
doesn't need to re-join back to the corpus CSVs every time.

Run (after network/citation_network/build_edges.py):
    python network/graph_construction/build_graphs.py
"""

import sys
import os
import pickle

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import networkx as nx

from config.paths import DATA_FINAL, OUTPUT_GRAPHS
from config.domains import get_domains, domain_to_filename, corpus_filename as get_corpus_filename

EDGES_DIR = os.path.join(os.path.dirname(__file__), "..", "citation_network")


def file_name_to_title(file_name: str) -> str:
    """Turns 'S_P_Gupta_vs_Union_Of_India_on_30_December_1981_1.PDF' into
    a readable label for later plotting/reporting."""
    name = file_name.replace(".PDF", "").replace(".pdf", "")
    name = name.replace("_", " ")
    return name


def build_domain_graph(domain: str, corpus_file: str):
    corpus_path = os.path.join(DATA_FINAL, corpus_file)
    edges_path = os.path.join(
        EDGES_DIR, f"{domain_to_filename(domain)}_edges_internal.csv"
    )

    if not os.path.exists(corpus_path) or not os.path.exists(edges_path):
        print(f"Skipping {domain} - missing corpus or edges file")
        return None

    corpus_df = pd.read_csv(corpus_path)
    edges_df = pd.read_csv(edges_path)

    G = nx.DiGraph()

    # Add ALL corpus judgments as nodes, even ones with no citation edges -
    # an isolated node is still a real judgment in the domain, and matters
    # for accurate density/coverage stats.
    for _, r in corpus_df.iterrows():
        G.add_node(
            r["file_name"],
            year=int(r["year"]) if pd.notna(r["year"]) else None,
            title=file_name_to_title(r["file_name"]),
        )

    # Add edges (both endpoints should already be nodes from the corpus,
    # but add_edge will create them if somehow missing)
    for _, r in edges_df.iterrows():
        G.add_edge(r["citing_file_name"], r["cited_file_name"])

    return G


def main():
    os.makedirs(OUTPUT_GRAPHS, exist_ok=True)
    summary_rows = []

    for domain in get_domains():
        print(f"\nBuilding graph: {domain}")
        G = build_domain_graph(domain, get_corpus_filename(domain))
        if G is None:
            continue

        n_nodes = G.number_of_nodes()
        n_edges = G.number_of_edges()
        density = nx.density(G)
        isolated = sum(1 for n in G.nodes() if G.degree(n) == 0)

        print(f"  Nodes: {n_nodes}")
        print(f"  Edges: {n_edges}")
        print(f"  Density: {density:.6f}")
        print(f"  Isolated nodes (no citations in/out): {isolated} ({isolated/n_nodes*100:.1f}%)")

        out_path = os.path.join(
            OUTPUT_GRAPHS, f"{domain_to_filename(domain)}_graph.gpickle"
        )
        with open(out_path, "wb") as f:
            pickle.dump(G, f)
        print(f"  Saved -> {out_path}")

        # Also save GraphML - human-readable, opens directly in Gephi if wanted
        graphml_path = os.path.join(
            OUTPUT_GRAPHS, f"{domain_to_filename(domain)}_graph.graphml"
        )
        nx.write_graphml(G, graphml_path)

        summary_rows.append({
            "domain": domain,
            "nodes": n_nodes,
            "edges": n_edges,
            "density": density,
            "isolated_nodes": isolated,
            "isolated_pct": round(isolated / n_nodes * 100, 1),
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_path = os.path.join(OUTPUT_GRAPHS, "graph_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"\nSummary comparison table -> {summary_path}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
