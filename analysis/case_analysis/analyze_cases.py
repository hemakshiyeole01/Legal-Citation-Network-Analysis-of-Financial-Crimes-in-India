"""
Stage: analysis/case_analysis (Phase 4 of Person A's track)

1. Top-N most influential cases per domain
2. Domain distribution over time (cases per decade, and as a share of ALL
   Supreme Court judgments that decade)
3. Age profile per domain

Influence is measured WITHIN the five domain corpora only (citations from the
other ~22,000 judgments in the dataset are not counted).

Run (after network/network_analysis/analyze_networks.py):
    python analysis/case_analysis/analyze_cases.py
    python analysis/case_analysis/analyze_cases.py --top 15

Output:
    output/tables/top_cases_by_domain.csv
    output/tables/domain_distribution_by_decade.csv
    output/tables/domain_age_profile.csv
    output/visualizations/domain_distribution_by_decade.png
"""

import sys
import os
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # write PNGs without needing a display
import matplotlib.pyplot as plt

from config.paths import OUTPUT_TABLES, OUTPUT_VISUALIZATIONS
from config.domains import get_domain_colors
from src.utils.analysis_io import (
    load_node_metrics, split_node_metrics, add_decade, all_judgments_per_decade,
)


def top_cases(per_domain: pd.DataFrame, combined: pd.DataFrame, n: int) -> pd.DataFrame:
    """Top-N cases per domain.

    Ranked by PageRank in the domain's own graph (a citation from an
    influential case counts for more), ties broken by citations received from
    all five domains. Both counts are shown so the ranking can be read
    critically. Only cases cited at least once by SOMEONE in the five domains
    are eligible - an uncited case isn't 'influential'."""
    from_all = combined.set_index("file_name")["in_degree"]
    frames = []
    for dom in sorted(per_domain["domain"].unique()):
        g = per_domain[per_domain["domain"] == dom].copy()
        g["citations_from_all_five_domains"] = g["file_name"].map(from_all).fillna(0).astype(int)
        g["citations_from_outside_this_domain"] = (
            g["citations_from_all_five_domains"] - g["in_degree"]).clip(lower=0)
        g = g[(g["in_degree"] > 0) | (g["citations_from_all_five_domains"] > 0)]
        g = g.sort_values(["pagerank", "citations_from_all_five_domains", "file_name"],
                          ascending=[False, False, True]).head(n)
        g.insert(1, "rank", range(1, len(g) + 1))
        frames.append(g)

    cols = ["domain", "rank", "title", "year", "case_domains",
            "in_degree", "citations_from_outside_this_domain",
            "citations_from_all_five_domains", "pagerank_x_N", "pagerank_rank", "file_name"]
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
    return out[cols].rename(columns={
        "in_degree": "citations_same_domain",
        "pagerank_rank": "pagerank_rank_in_domain",
    })


def decade_distribution(per_domain: pd.DataFrame, sc_per_decade) -> pd.DataFrame:
    d = add_decade(per_domain)
    domains = sorted(d["domain"].unique())
    decades = list(range(int(d["decade"].min()), int(d["decade"].max()) + 1, 10))
    counts = d.groupby(["domain", "decade"]).size()
    idx = pd.MultiIndex.from_product([domains, decades], names=["domain", "decade"])
    out = counts.reindex(idx, fill_value=0).rename("cases").reset_index()
    out["pct_of_domain"] = 100 * out["cases"] / out.groupby("domain")["cases"].transform("sum")
    out["decade_label"] = out["decade"].astype(str) + "s"
    if sc_per_decade is not None:
        out["all_sc_judgments_in_decade"] = out["decade"].map(sc_per_decade).fillna(0).astype(int)
        denom = out["all_sc_judgments_in_decade"].replace(0, np.nan)
        out["pct_of_all_sc_judgments"] = 100 * out["cases"] / denom
    return out


def age_profile(per_domain: pd.DataFrame) -> pd.DataFrame:
    d = per_domain.dropna(subset=["year"]).copy()
    d["year"] = d["year"].astype(int)
    rows = []
    for dom, g in d.groupby("domain"):
        rows.append({
            "domain": dom,
            "cases": len(g),
            "first_year": int(g["year"].min()),
            "median_year": float(g["year"].median()),
            "last_year": int(g["year"].max()),
            "pct_before_1980": 100 * (g["year"] < 1980).mean(),
            "pct_1980_to_1999": 100 * ((g["year"] >= 1980) & (g["year"] < 2000)).mean(),
            "pct_2000_onward": 100 * (g["year"] >= 2000).mean(),
        })
    return pd.DataFrame(rows)


def plot_distribution(dist: pd.DataFrame, path: str):
    colors = get_domain_colors()
    has_share = "pct_of_all_sc_judgments" in dist.columns
    fig, axes = plt.subplots(1, 2 if has_share else 1, figsize=(13 if has_share else 7, 4.8))
    axes = np.atleast_1d(axes)

    for dom, g in dist.groupby("domain"):
        axes[0].plot(g["decade"], g["cases"], marker="o", label=dom, color=colors.get(dom))
        if has_share:
            axes[1].plot(g["decade"], g["pct_of_all_sc_judgments"], marker="o",
                         label=dom, color=colors.get(dom))
    axes[0].set_title("Cases per decade")
    axes[0].set_ylabel("judgments in domain")
    if has_share:
        axes[1].set_title("Share of ALL Supreme Court judgments that decade")
        axes[1].set_ylabel("% of that decade's judgments")
    for ax in axes:
        ax.set_xlabel("decade (2020s = 2020-2025)")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=10, help="cases per domain (default 10)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_TABLES, exist_ok=True)
    os.makedirs(OUTPUT_VISUALIZATIONS, exist_ok=True)

    nm = load_node_metrics()
    per_domain, combined = split_node_metrics(nm)

    top = top_cases(per_domain, combined, args.top)
    top.round(6).to_csv(os.path.join(OUTPUT_TABLES, "top_cases_by_domain.csv"), index=False)
    print(f"Saved {len(top)} rows -> output/tables/top_cases_by_domain.csv")
    for dom in sorted(per_domain["domain"].unique()):
        g = top[top["domain"] == dom]
        if g.empty:
            print(f"\n{dom}: no case is cited by any other case in the five domains")
            continue
        print(f"\n{dom} - top {min(3, len(g))} of {len(g)}:")
        for _, r in g.head(3).iterrows():
            print(f"  #{r['rank']}  {str(r['title'])[:62]} ({r['year']})  "
                  f"same-domain {r['citations_same_domain']}, all five {r['citations_from_all_five_domains']}")

    sc = all_judgments_per_decade()
    if sc is None:
        print("\nNote: data/processed/all_judgments_cleaned.csv not found - "
              "skipping the 'share of all Supreme Court judgments' column.")
    dist = decade_distribution(per_domain, sc)
    dist.round(4).to_csv(os.path.join(OUTPUT_TABLES, "domain_distribution_by_decade.csv"), index=False)
    print("Saved output/tables/domain_distribution_by_decade.csv")

    prof = age_profile(per_domain)
    prof.round(3).to_csv(os.path.join(OUTPUT_TABLES, "domain_age_profile.csv"), index=False)
    print("Saved output/tables/domain_age_profile.csv")
    print(prof.round(1).to_string(index=False))

    fig_path = os.path.join(OUTPUT_VISUALIZATIONS, "domain_distribution_by_decade.png")
    plot_distribution(dist, fig_path)
    print(f"Saved {fig_path}")


if __name__ == "__main__":
    main()
