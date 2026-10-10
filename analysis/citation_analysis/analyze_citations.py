"""
Stage: analysis/citation_analysis (Phase 5 of Person A's track)

1. Most-cited judgments - overall (across all five domains) and per domain
2. Citation trend over time - how many citations the cases of each decade
   make, per case
3. Average citations per case per domain, with 95% bootstrap intervals

All counts are WITHIN the five domain corpora (citations from the other
~22,000 judgments in the dataset are not counted).

Run (after network/network_analysis/analyze_networks.py):
    python analysis/citation_analysis/analyze_citations.py

Output:
    output/tables/most_cited_overall.csv
    output/tables/most_cited_by_domain.csv
    output/tables/citation_trend_by_decade.csv
    output/tables/average_citations_per_case.csv
    output/visualizations/citation_intensity_by_decade.png
"""

import sys
import os
import pickle
from collections import defaultdict

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.paths import OUTPUT_GRAPHS, OUTPUT_TABLES, OUTPUT_VISUALIZATIONS
from config.domains import get_domains, domain_to_filename, get_domain_colors
from src.utils.analysis_io import (
    COMBINED_NAME, load_node_metrics, split_node_metrics, bootstrap_ci,
)

TOP_OVERALL = 20
TOP_PER_DOMAIN = 10
MIN_CASES_FOR_TREND_POINT = 20  # a decade with fewer cases is too noisy to plot


def load_graph(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def load_all_graphs() -> dict:
    graphs = {}
    for d in get_domains():
        G = load_graph(os.path.join(OUTPUT_GRAPHS, f"{domain_to_filename(d)}_graph.gpickle"))
        if G is not None:
            graphs[d] = G
    C = load_graph(os.path.join(OUTPUT_GRAPHS, "combined_cross_domain_graph.gpickle"))
    if C is not None:
        graphs[COMBINED_NAME] = C
    return graphs


def edge_lags(G) -> list:
    """Years between citing and cited case (non-negative only)."""
    lags = []
    for u, v in G.edges():
        yu, yv = G.nodes[u].get("year"), G.nodes[v].get("year")
        if yu is not None and yv is not None and yu >= yv:
            lags.append(yu - yv)
    return lags


def most_cited_overall(combined: pd.DataFrame, n: int) -> pd.DataFrame:
    g = combined.sort_values(["in_degree", "pagerank", "file_name"],
                             ascending=[False, False, True])
    g = g[g["in_degree"] > 0].head(n).copy()
    g.insert(0, "rank", range(1, len(g) + 1))
    return g[["rank", "title", "year", "case_domains", "in_degree",
              "pagerank_x_N", "file_name"]].rename(
        columns={"in_degree": "citations_from_all_five_domains"})


def most_cited_by_domain(per_domain: pd.DataFrame, combined: pd.DataFrame, n: int) -> pd.DataFrame:
    from_all = combined.set_index("file_name")["in_degree"]
    frames = []
    for dom in sorted(per_domain["domain"].unique()):
        g = per_domain[per_domain["domain"] == dom].copy()
        g["citations_from_all_five_domains"] = g["file_name"].map(from_all).fillna(0).astype(int)
        g = g[g["in_degree"] > 0].sort_values(
            ["in_degree", "citations_from_all_five_domains", "pagerank", "file_name"],
            ascending=[False, False, False, True]).head(n)
        g.insert(1, "rank", range(1, len(g) + 1))
        frames.append(g)
    cols = ["domain", "rank", "title", "year", "in_degree",
            "citations_from_all_five_domains", "file_name"]
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
    return out[cols].rename(columns={"in_degree": "citations_same_domain"})


def citation_trend(graphs: dict) -> pd.DataFrame:
    """Per graph and decade: how many cases were decided, how many citations
    those cases MAKE (to older cases in the same graph), and per case."""
    rows = []
    for name, G in graphs.items():
        cases, edges, citing = defaultdict(int), defaultdict(int), defaultdict(int)
        for node, attrs in G.nodes(data=True):
            y = attrs.get("year")
            if y is None:
                continue
            dec = (int(y) // 10) * 10
            out = G.out_degree(node)
            cases[dec] += 1
            edges[dec] += out
            citing[dec] += 1 if out > 0 else 0
        for dec in sorted(cases):
            rows.append({
                "domain": name,
                "decade": dec,
                "decade_label": f"{dec}s",
                "cases": cases[dec],
                "citations_made": edges[dec],
                "citations_per_case": edges[dec] / cases[dec],
                "cases_that_cite": citing[dec],
                "pct_cases_that_cite": 100 * citing[dec] / cases[dec],
            })
    return pd.DataFrame(rows)


def average_citations(per_domain: pd.DataFrame, combined: pd.DataFrame, graphs: dict) -> pd.DataFrame:
    from_all = combined.set_index("file_name")["in_degree"]
    rows = []

    def row(name, same, all_five, out_deg, lags):
        lo, hi = bootstrap_ci(same)
        lo5, hi5 = bootstrap_ci(all_five)
        llo, lhi = bootstrap_ci(lags, stat="median")
        n = len(same)
        return {
            "domain": name,
            "cases": n,
            "mean_citations_same_domain": same.mean() if n else np.nan,
            "same_domain_ci_low": lo, "same_domain_ci_high": hi,
            "pct_cited_same_domain": 100 * (same > 0).mean() if n else np.nan,
            "mean_citations_from_all_five_domains": all_five.mean() if n else np.nan,
            "all_five_ci_low": lo5, "all_five_ci_high": hi5,
            "pct_cited_by_any_of_five": 100 * (all_five > 0).mean() if n else np.nan,
            "mean_citations_made_same_domain": out_deg.mean() if n else np.nan,
            "median_citation_lag_years": float(np.median(lags)) if len(lags) else np.nan,
            "lag_ci_low": llo, "lag_ci_high": lhi,
            "citation_edges": len(lags),
        }

    for dom in sorted(per_domain["domain"].unique()):
        g = per_domain[per_domain["domain"] == dom]
        same = g["in_degree"].to_numpy(float)
        all_five = np.maximum(g["file_name"].map(from_all).fillna(0).to_numpy(float), same)
        lags = edge_lags(graphs[dom]) if dom in graphs else []
        rows.append(row(dom, same, all_five, g["out_degree"].to_numpy(float), lags))

    # Combined: every case once; same-domain == all-five by definition
    cin = combined["in_degree"].to_numpy(float)
    clags = edge_lags(graphs[COMBINED_NAME]) if COMBINED_NAME in graphs else []
    rows.append(row(COMBINED_NAME, cin, cin, combined["out_degree"].to_numpy(float), clags))
    return pd.DataFrame(rows)


def plot_intensity(trend: pd.DataFrame, path: str):
    colors = get_domain_colors()
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for dom, g in trend.groupby("domain"):
        if dom == COMBINED_NAME:
            continue
        g = g[g["cases"] >= MIN_CASES_FOR_TREND_POINT]
        if len(g):
            ax.plot(g["decade"], g["citations_per_case"], marker="o", label=dom,
                    color=colors.get(dom))
    ax.set_title("Citations made per case, by decade the case was decided\n"
                 f"(only decades with at least {MIN_CASES_FOR_TREND_POINT} cases; within-domain citations)")
    ax.set_xlabel("decade (2020s = 2020-2025)")
    ax.set_ylabel("citations to older cases in the same domain, per case")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    os.makedirs(OUTPUT_TABLES, exist_ok=True)
    os.makedirs(OUTPUT_VISUALIZATIONS, exist_ok=True)

    nm = load_node_metrics()
    per_domain, combined = split_node_metrics(nm)
    graphs = load_all_graphs()
    if not graphs:
        sys.exit("No graphs found in output/graphs/ - run network/graph_construction/ first.")

    overall = most_cited_overall(combined, TOP_OVERALL)
    overall.round(6).to_csv(os.path.join(OUTPUT_TABLES, "most_cited_overall.csv"), index=False)
    print(f"Saved {len(overall)} rows -> output/tables/most_cited_overall.csv")
    for _, r in overall.head(5).iterrows():
        print(f"  #{r['rank']}  {str(r['title'])[:60]} ({r['year']})  "
              f"{r['citations_from_all_five_domains']} citations  [{r['case_domains']}]")

    bydom = most_cited_by_domain(per_domain, combined, TOP_PER_DOMAIN)
    bydom.round(6).to_csv(os.path.join(OUTPUT_TABLES, "most_cited_by_domain.csv"), index=False)
    print(f"Saved {len(bydom)} rows -> output/tables/most_cited_by_domain.csv")

    trend = citation_trend(graphs)
    trend.round(4).to_csv(os.path.join(OUTPUT_TABLES, "citation_trend_by_decade.csv"), index=False)
    print(f"Saved {len(trend)} rows -> output/tables/citation_trend_by_decade.csv")

    avg = average_citations(per_domain, combined, graphs)
    avg.round(4).to_csv(os.path.join(OUTPUT_TABLES, "average_citations_per_case.csv"), index=False)
    print("Saved output/tables/average_citations_per_case.csv\n")
    show = avg[["domain", "cases", "mean_citations_same_domain", "same_domain_ci_low",
                "same_domain_ci_high", "mean_citations_from_all_five_domains",
                "median_citation_lag_years"]].round(3)
    print(show.to_string(index=False))

    fig_path = os.path.join(OUTPUT_VISUALIZATIONS, "citation_intensity_by_decade.png")
    plot_intensity(trend, fig_path)
    print(f"\nSaved {fig_path}")


if __name__ == "__main__":
    main()
