"""
Stage: network/network_analysis (Phase 3 of Person A's track)

Computes, for each domain graph and for the combined all-domain graph:
  1. Structural metrics per graph (size, connectivity, path length, citation lag)
  2. Per-case influence metrics (in-degree, PageRank)
  3. Cumulative temporal snapshots (how the network grew, decade by decade)
  4. Influence trajectories for each graph's top cases (how their standing
     developed over time)

Run (after output/graphs/ has been rebuilt by network/graph_construction/):
    python network/network_analysis/analyze_networks.py

Output (output/tables/):
    network_metrics_by_domain.csv   one row per graph
    node_metrics.csv                one row per case per graph
    temporal_metrics.csv            one row per graph per snapshot year
    top_case_trajectories.csv       top cases' cumulative standing per snapshot
"""

import sys
import os
import pickle
import random

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import networkx as nx

from config.paths import OUTPUT_GRAPHS, OUTPUT_TABLES
from config.domains import get_domains, domain_to_filename

COMBINED_NAME = "Combined (all domains)"
SNAPSHOT_DECADES = list(range(1960, 2021, 10))
TOP_N_TRAJECTORY = 10
PAGERANK_ALPHA = 0.85

# Average path length is computed on the largest weakly-connected component
# (as an undirected graph - directed paths between random cases mostly don't
# exist in a citation DAG). Exact for components up to this size; above it,
# estimated from a random sample of source nodes to keep runtime bounded.
MAX_EXACT_PATH_NODES = 3000
PATH_SAMPLE_SOURCES = 300
RANDOM_SEED = 42


def load_graph(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def safe_pagerank(G):
    """PageRank over citing -> cited edges, so rank flows to the cited case:
    a case cited by influential cases scores higher than one cited by obscure
    cases. Isolated nodes get the baseline (teleport) share."""
    if G.number_of_nodes() == 0:
        return {}
    try:
        return nx.pagerank(G, alpha=PAGERANK_ALPHA)
    except nx.PowerIterationFailedConvergence:
        return nx.pagerank(G, alpha=PAGERANK_ALPHA, max_iter=1000)


def edge_lags(G):
    """Years between a citing case and the case it cites.
    Returns (list of non-negative lags, count of edges where the CITED case
    is newer than the citing one - a data anomaly worth reporting)."""
    lags, future = [], 0
    for u, v in G.edges():
        yu, yv = G.nodes[u].get("year"), G.nodes[v].get("year")
        if yu is None or yv is None:
            continue
        if yu - yv < 0:
            future += 1
        else:
            lags.append(yu - yv)
    return lags, future


def path_stats(H_directed):
    """(average shortest path, longest shortest path, method) on the
    undirected version of a connected graph."""
    H = H_directed.to_undirected()
    nodes = list(H.nodes())
    if len(nodes) < 2:
        return None, None, "n/a"
    exact = len(nodes) <= MAX_EXACT_PATH_NODES
    sources = nodes if exact else random.Random(RANDOM_SEED).sample(nodes, PATH_SAMPLE_SOURCES)
    total = count = longest = 0
    for s in sources:
        d = nx.single_source_shortest_path_length(H, s)
        total += sum(d.values())
        count += len(d) - 1
        longest = max(longest, max(d.values()))
    method = "exact" if exact else f"sampled ({len(sources)} sources)"
    return total / count, longest, method


def domain_metrics(name, G):
    n, e = G.number_of_nodes(), G.number_of_edges()
    in_deg, out_deg = dict(G.in_degree()), dict(G.out_degree())
    comps = sorted(nx.weakly_connected_components(G), key=len, reverse=True)
    lcc_nodes = len(comps[0]) if comps else 0
    if lcc_nodes >= 2:
        avg_path, longest, method = path_stats(G.subgraph(comps[0]))
    else:
        avg_path, longest, method = None, None, "n/a"

    years = [d["year"] for _, d in G.nodes(data=True) if d.get("year") is not None]
    lags, future = edge_lags(G)

    def pct(k):
        return 100 * k / n if n else 0.0

    return {
        "domain": name,
        "nodes": n,
        "edges": e,
        "density": nx.density(G) if n > 1 else 0.0,
        "mean_in_degree": e / n if n else 0.0,
        "max_in_degree": max(in_deg.values()) if in_deg else 0,
        "pct_cited_at_least_once": pct(sum(1 for v in in_deg.values() if v > 0)),
        "pct_citing_at_least_once": pct(sum(1 for v in out_deg.values() if v > 0)),
        "pct_isolated": pct(sum(1 for x in G.nodes() if in_deg[x] + out_deg[x] == 0)),
        "weak_components": len(comps),
        "nontrivial_components": sum(1 for c in comps if len(c) > 1),
        "largest_component_nodes": lcc_nodes,
        "largest_component_pct": pct(lcc_nodes),
        "avg_path_length_largest_component": avg_path,
        "longest_shortest_path_largest_component": longest,
        "path_method": method,
        "median_judgment_year": float(pd.Series(years).median()) if years else None,
        "median_citation_lag_years": float(pd.Series(lags).median()) if lags else None,
        "mean_citation_lag_years": float(pd.Series(lags).mean()) if lags else None,
        "edges_citing_a_newer_case": future,
        "nodes_missing_year": n - len(years),
    }


def node_metrics(name, G):
    """One row per case. pagerank_x_N rescales PageRank so 1.0 = an average
    case in that graph - raw PageRank shrinks as a graph grows, so raw values
    are not comparable between a 42-node and a 2,000-node domain."""
    n = G.number_of_nodes()
    pr = safe_pagerank(G)
    rows = []
    for node, attrs in G.nodes(data=True):
        rows.append({
            "domain": name,
            "file_name": node,
            "title": attrs.get("title", node),
            "year": attrs.get("year"),
            "case_domains": attrs.get("domain", name),
            "in_degree": G.in_degree(node),
            "out_degree": G.out_degree(node),
            "pagerank": pr[node],
            "pagerank_x_N": pr[node] * n,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values(["pagerank", "in_degree", "file_name"], ascending=[False, False, True])
    df["pagerank_rank"] = df["pagerank"].rank(method="min", ascending=False).astype(int)
    df["in_degree_rank"] = df["in_degree"].rank(method="min", ascending=False).astype(int)
    return df.reset_index(drop=True)


def snapshot(G, year):
    """Cumulative graph of everything decided up to and including `year`."""
    keep = [n for n, d in G.nodes(data=True) if d.get("year") is not None and d["year"] <= year]
    return G.subgraph(keep)


def temporal_rows(name, G, snapshots):
    rows, prev_nodes = [], 0
    for t in snapshots:
        S = snapshot(G, t)
        n, e = S.number_of_nodes(), S.number_of_edges()
        cited = sum(1 for _, d in S.in_degree() if d > 0)
        rows.append({
            "domain": name,
            "snapshot_year": t,
            "nodes": n,
            "new_nodes_since_previous": n - prev_nodes,
            "edges": e,
            "mean_in_degree": e / n if n else 0.0,
            "pct_cited_at_least_once": 100 * cited / n if n else 0.0,
        })
        prev_nodes = n
    return rows


def trajectory_rows(name, G, node_df, snapshots):
    """How the final top cases' standing developed: their cumulative citation
    count and PageRank at each snapshot (blank before the case existed)."""
    if node_df.empty:
        return []
    top = node_df[node_df["in_degree"] > 0].head(TOP_N_TRAJECTORY)
    rows = []
    for t in snapshots:
        S = snapshot(G, t)
        pr, n = safe_pagerank(S), S.number_of_nodes()
        for _, case in top.iterrows():
            present = case["file_name"] in S
            rows.append({
                "domain": name,
                "file_name": case["file_name"],
                "title": case["title"],
                "case_year": case["year"],
                "final_rank_by_pagerank": case["pagerank_rank"],
                "snapshot_year": t,
                "cumulative_in_degree": S.in_degree(case["file_name"]) if present else None,
                "pagerank_x_N": pr[case["file_name"]] * n if present else None,
            })
    return rows


def main():
    os.makedirs(OUTPUT_TABLES, exist_ok=True)

    graphs = {}
    for d in get_domains():
        path = os.path.join(OUTPUT_GRAPHS, f"{domain_to_filename(d)}_graph.gpickle")
        G = load_graph(path)
        if G is None:
            print(f"Skipping {d} - graph not found: {path}")
        else:
            graphs[d] = G
    combined = load_graph(os.path.join(OUTPUT_GRAPHS, "combined_cross_domain_graph.gpickle"))
    if combined is not None:
        graphs[COMBINED_NAME] = combined
    else:
        print("Skipping combined graph - not found")

    if not graphs:
        sys.exit("No graphs found. Run network/graph_construction/ first.")

    all_years = [d["year"] for G in graphs.values() for _, d in G.nodes(data=True)
                 if d.get("year") is not None]
    if not all_years:
        sys.exit("No node has a year attribute - cannot build temporal snapshots.")
    global_max = max(all_years)
    snapshots = sorted({y for y in SNAPSHOT_DECADES if y < global_max} | {global_max})
    print(f"Snapshot years: {snapshots}")

    metric_rows, node_frames, temporal, trajectories = [], [], [], []
    for name, G in graphs.items():
        print(f"\nAnalyzing: {name} ({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)")
        metric_rows.append(domain_metrics(name, G))
        ndf = node_metrics(name, G)
        node_frames.append(ndf)
        temporal.extend(temporal_rows(name, G, snapshots))
        trajectories.extend(trajectory_rows(name, G, ndf, snapshots))

    metrics_df = pd.DataFrame(metric_rows)
    node_df = pd.concat(node_frames, ignore_index=True)
    temporal_df = pd.DataFrame(temporal)
    traj_df = pd.DataFrame(trajectories)

    outputs = {
        "network_metrics_by_domain.csv": metrics_df,
        "node_metrics.csv": node_df,
        "temporal_metrics.csv": temporal_df,
        "top_case_trajectories.csv": traj_df,
    }
    for fname, df in outputs.items():
        df.round(6).to_csv(os.path.join(OUTPUT_TABLES, fname), index=False)
        print(f"Saved {len(df):>6} rows -> output/tables/{fname}")

    show = ["domain", "nodes", "edges", "mean_in_degree", "pct_cited_at_least_once",
            "pct_isolated", "largest_component_nodes", "avg_path_length_largest_component",
            "median_citation_lag_years", "edges_citing_a_newer_case"]
    print("\n" + metrics_df[show].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
