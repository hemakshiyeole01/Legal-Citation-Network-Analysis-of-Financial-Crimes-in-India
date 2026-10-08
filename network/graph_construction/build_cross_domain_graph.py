"""
Stage: network/graph_construction (Phase 2b - cross-domain view)

The per-domain graphs (build_graphs.py) only use INTERNAL edges - same
domain on both sides - so cross-domain citations (e.g. a Digital Fraud
case citing a Financial Fraud case) never appear anywhere. This script
builds a SECOND graph that includes both INTERNAL and CROSS_DOMAIN edges
across all 3 domains together, plus a domain-to-domain citation matrix
that directly answers "which domain cites which domain, and how much".

Run (after network/citation_network/build_edges.py):
    python network/graph_construction/build_cross_domain_graph.py
"""

import sys
import os
import pickle

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import networkx as nx

from config.paths import DATA_FINAL, OUTPUT_GRAPHS, OUTPUT_TABLES
from config.domains import get_domains, domain_to_filename, corpus_filename as get_corpus_filename

EDGES_DIR = os.path.join(os.path.dirname(__file__), "..", "citation_network")


def file_name_to_title(file_name: str) -> str:
    return file_name.replace(".PDF", "").replace(".pdf", "").replace("_", " ")


def main():
    os.makedirs(OUTPUT_GRAPHS, exist_ok=True)
    os.makedirs(OUTPUT_TABLES, exist_ok=True)

    G = nx.DiGraph()
    all_edges = []

    # Add nodes from every domain, tagged with which domain(s) they belong
    # to. A judgment can legitimately match more than one domain - store
    # all of them (semicolon-joined) rather than letting the last domain
    # processed silently overwrite the others.
    node_domains = {}
    node_attrs = {}
    for domain in get_domains():
        corpus_path = os.path.join(DATA_FINAL, get_corpus_filename(domain))
        if not os.path.exists(corpus_path):
            print(f"Skipping {domain} nodes - corpus file not found")
            continue
        corpus_df = pd.read_csv(corpus_path)
        for _, r in corpus_df.iterrows():
            fname = r["file_name"]
            node_domains.setdefault(fname, set()).add(domain)
            node_attrs[fname] = {
                "year": int(r["year"]) if pd.notna(r["year"]) else None,
                "title": file_name_to_title(fname),
            }
        print(f"{domain}: {len(corpus_df)} nodes added")

    for fname, domains in node_domains.items():
        G.add_node(
            fname,
            domain="; ".join(sorted(domains)),
            **node_attrs[fname],
        )

    # Add edges - both INTERNAL and CROSS_DOMAIN (both have real endpoints
    # inside our 3 domains; OUTSIDE_DOMAINS and UNRESOLVED don't)
    for domain in get_domains():
        edges_path = os.path.join(
            EDGES_DIR, f"{domain_to_filename(domain)}_edges_all.csv"
        )
        if not os.path.exists(edges_path):
            print(f"Skipping {domain} edges - file not found")
            continue

        edges_df = pd.read_csv(edges_path)
        relevant = edges_df[edges_df["edge_type"].isin(["INTERNAL", "CROSS_DOMAIN"])]
        relevant = relevant.drop_duplicates(subset=["citing_file_name", "cited_file_name"])

        for _, r in relevant.iterrows():
            G.add_edge(r["citing_file_name"], r["cited_file_name"])
            all_edges.append({
                "citing_domain": domain,
                "cited_domain": r["cited_domain"],
                "edge_type": r["edge_type"],
            })

    print(f"\nCombined graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    graph_path = os.path.join(OUTPUT_GRAPHS, "combined_cross_domain_graph.gpickle")
    with open(graph_path, "wb") as f:
        pickle.dump(G, f)
    print(f"Saved graph -> {graph_path}")

    graphml_path = os.path.join(OUTPUT_GRAPHS, "combined_cross_domain_graph.graphml")
    nx.write_graphml(G, graphml_path)

    # Domain-to-domain citation matrix - this is what directly answers
    # "which domain cites which domain, and how much". Explode multi-domain
    # cited_domain values (e.g. "Corruption; Financial Fraud") into separate
    # rows so each domain gets counted, rather than forming its own column.
    edges_df_all = pd.DataFrame(all_edges)
    if len(edges_df_all):
        edges_df_all["cited_domain"] = edges_df_all["cited_domain"].str.split("; ")
        edges_df_all = edges_df_all.explode("cited_domain").reset_index(drop=True)

        matrix = pd.crosstab(edges_df_all["citing_domain"], edges_df_all["cited_domain"])
        matrix_path = os.path.join(OUTPUT_TABLES, "domain_citation_matrix.csv")
        matrix.to_csv(matrix_path)
        print(f"\nDomain-to-domain citation matrix (rows=citing, cols=cited):")
        print(matrix.to_string())
        print(f"\nSaved -> {matrix_path}")


if __name__ == "__main__":
    main()
