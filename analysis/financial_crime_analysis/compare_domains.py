"""
Stage: analysis/financial_crime_analysis (Phase 6 of Person A's track)

The cross-domain comparison - the project's "so what".

New measure here: AGE- AND SIZE-ADJUSTED INSULARITY (observed / expected).
  For each citation a domain's case makes to another case inside the five
  domains, ask: how likely was it to land in the SAME domain by chance, given
  how many older cases each domain had available at that moment? Sum that
  over all citations = expected own-domain citations. Observed / expected:
     1.0  = no preference for its own domain
     >1   = cites its own domain more than chance
     <1   = cites other domains more than chance
  This removes the two things that made raw comparisons misleading: domain
  size (a domain holding half the cases will cite itself a lot by chance) and
  era (a domain cannot cite cases that didn't exist yet).

Run (after Phases 3, 4 and 5):
    python analysis/financial_crime_analysis/compare_domains.py

Output:
    output/tables/insularity_by_domain.csv
    output/tables/domain_comparison.csv
    output/visualizations/domain_comparison.png
    output/reports/results_summary.md   (auto-generated draft - review it)
"""

import sys
import os
import datetime
import textwrap

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.paths import (PROJECT_ROOT, OUTPUT_TABLES, OUTPUT_VISUALIZATIONS, OUTPUT_REPORTS)
from config.domains import get_domains, domain_to_filename, get_domain_colors
from src.utils.analysis_io import (
    COMBINED_NAME, load_node_metrics, split_node_metrics, table_path, require,
)

EDGES_DIR = os.path.join(PROJECT_ROOT, "network", "citation_network")
SMALL_DOMAIN_CASES = 100   # below this, a domain is described but not ranked
# A ratio observed/expected is meaningless when almost nothing was expected:
# seeing 0 own-domain links when chance predicts 0.3 says nothing at all (and
# the bootstrap interval collapses to 0-0, which looks falsely certain).
MIN_EXPECTED_OWN = 5.0
N_BOOT = 2000
SEED = 42


# ---------------------------------------------------------------- insularity

def build_universe(combined: pd.DataFrame) -> pd.DataFrame:
    u = combined[["file_name", "year", "case_domains"]].dropna(subset=["year"]).copy()
    u["year"] = u["year"].astype(int)
    u["domains"] = u["case_domains"].astype(str).str.split("; ").apply(set)
    return u.reset_index(drop=True)


class EligibleShare:
    """p(domain, year): of all five-domain cases decided up to `year`, what
    fraction belongs to `domain`? = the chance a citation made in `year`
    lands in that domain if it picked an older case at random."""

    def __init__(self, universe: pd.DataFrame, domains):
        self.y0 = int(universe["year"].min())
        self.n = int(universe["year"].max()) - self.y0 + 1
        off = universe["year"].to_numpy() - self.y0
        self.total = np.cumsum(np.bincount(off, minlength=self.n))
        self.dom = {}
        for d in domains:
            mask = universe["domains"].apply(lambda s, d=d: d in s).to_numpy()
            self.dom[d] = np.cumsum(np.bincount(off[mask], minlength=self.n))

    def p(self, domain, year) -> float:
        i = min(max(int(year) - self.y0, 0), self.n - 1)
        t = self.total[i]
        return float(self.dom[domain][i] / t) if t else float("nan")


def insularity(domain: str, share: EligibleShare, year_map: dict, edges_path: str):
    row = {"domain": domain}
    if not os.path.exists(edges_path):
        return None
    e = pd.read_csv(edges_path, usecols=["citing_file_name", "cited_file_name", "edge_type"])
    # unique citing->cited pairs: a case citing the same precedent five times is one link
    e = e[e["cited_file_name"].notna()].drop_duplicates(["citing_file_name", "cited_file_name"])

    n_int = int((e["edge_type"] == "INTERNAL").sum())
    n_cross = int((e["edge_type"] == "CROSS_DOMAIN").sum())
    n_out = int((e["edge_type"] == "OUTSIDE_DOMAINS").sum())
    resolved = n_int + n_cross + n_out
    row.update({
        "resolved_citation_links": resolved,
        "pct_to_own_domain": 100 * n_int / resolved if resolved else np.nan,
        "pct_to_other_domains": 100 * n_cross / resolved if resolved else np.nan,
        "pct_outside_the_five_domains": 100 * n_out / resolved if resolved else np.nan,
    })

    within = e[e["edge_type"].isin(["INTERNAL", "CROSS_DOMAIN"])].copy()
    within["year"] = within["citing_file_name"].map(year_map)
    within = within.dropna(subset=["year"])
    row.update({"links_inside_five_domains": len(within), "observed_own_domain": 0,
                "expected_own_domain": np.nan, "insularity_ratio": np.nan,
                "ratio_ci_low": np.nan, "ratio_ci_high": np.nan,
                "expected_too_small": True})
    if within.empty:
        return row

    within["is_own"] = (within["edge_type"] == "INTERNAL").astype(int)
    per = within.groupby("citing_file_name").agg(
        links=("is_own", "size"), observed=("is_own", "sum"), year=("year", "first"))
    p = np.array([share.p(domain, y) for y in per["year"]])
    obs = per["observed"].to_numpy(float)
    exp = per["links"].to_numpy(float) * p

    row["observed_own_domain"] = int(obs.sum())
    row["expected_own_domain"] = float(exp.sum())
    row["expected_too_small"] = bool(exp.sum() < MIN_EXPECTED_OWN)
    if exp.sum() > 0:
        row["insularity_ratio"] = float(obs.sum() / exp.sum())
        # bootstrap over CITING CASES (links from one case aren't independent)
        rng = np.random.default_rng(SEED)
        idx = rng.integers(0, len(per), size=(N_BOOT, len(per)))
        num, den = obs[idx].sum(axis=1), exp[idx].sum(axis=1)
        ok = den > 0
        if ok.any():
            lo, hi = np.percentile(num[ok] / den[ok], [2.5, 97.5])
            row["ratio_ci_low"], row["ratio_ci_high"] = float(lo), float(hi)
    return row


# ------------------------------------------------------------------ assembly

def build_comparison(netm, avg, ages, top, ins) -> pd.DataFrame:
    ins = ins.copy()
    too_small = ins["expected_too_small"].fillna(True).astype(bool)
    ins.loc[too_small, ["insularity_ratio", "ratio_ci_low", "ratio_ci_high"]] = np.nan
    base = netm[netm["domain"] != COMBINED_NAME][[
        "domain", "nodes", "edges", "density", "pct_isolated", "largest_component_nodes"]]
    base = base.rename(columns={"nodes": "cases", "edges": "internal_citation_links"})

    a = avg[avg["domain"] != COMBINED_NAME][[
        "domain", "mean_citations_same_domain", "same_domain_ci_low", "same_domain_ci_high",
        "pct_cited_same_domain", "mean_citations_from_all_five_domains",
        "median_citation_lag_years", "lag_ci_low", "lag_ci_high"]]
    out = base.merge(a, on="domain", how="left")
    out = out.merge(ages[["domain", "median_year", "pct_2000_onward"]], on="domain", how="left")
    out = out.merge(ins[["domain", "pct_to_own_domain", "pct_to_other_domains",
                         "pct_outside_the_five_domains", "insularity_ratio",
                         "ratio_ci_low", "ratio_ci_high"]], on="domain", how="left")

    first = top[top["rank"] == 1][["domain", "title", "year", "citations_same_domain"]]
    first = first.rename(columns={"title": "top_case", "year": "top_case_year",
                                  "citations_same_domain": "top_case_citations"})
    return out.merge(first, on="domain", how="left")


def fmt_ci(v, lo, hi, nd=2):
    if pd.isna(v):
        return "n/a"
    return f"{v:.{nd}f} ({lo:.{nd}f}-{hi:.{nd}f})"


def md_table(headers, rows) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def plot_comparison(comp: pd.DataFrame, path: str):
    colors = get_domain_colors()
    c = comp.sort_values("domain").reset_index(drop=True)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    x = np.arange(len(c))
    m = c["mean_citations_same_domain"].to_numpy(float)
    err = np.vstack([m - c["same_domain_ci_low"].to_numpy(float),
                     c["same_domain_ci_high"].to_numpy(float) - m])
    axes[0].bar(x, m, color=[colors.get(d) for d in c["domain"]], yerr=err, capsize=4)
    axes[0].set_title("Average citations received per case\nfrom cases in the same domain (95% interval)")
    axes[0].set_ylabel("citations per case")

    r = c["insularity_ratio"].to_numpy(float)
    rerr = np.vstack([r - c["ratio_ci_low"].to_numpy(float), c["ratio_ci_high"].to_numpy(float) - r])
    rerr = np.nan_to_num(rerr)
    axes[1].bar(x, np.nan_to_num(r), color=[colors.get(d) for d in c["domain"]], yerr=rerr, capsize=4)
    for xi, ri in zip(x, r):
        if np.isnan(ri):
            axes[1].text(xi, 0.05, "n/a\n(too few\nexpected)", ha="center", va="bottom", fontsize=7)
    axes[1].axhline(1.0, color="black", linestyle="--", linewidth=1)
    axes[1].set_title("Own-domain citation rate vs chance\n(age- and size-adjusted; 1.0 = no preference)")
    axes[1].set_ylabel("observed / expected")

    for xi, mi in zip(x, m):
        if mi == 0:
            axes[0].text(xi, 0.003, "none\nobserved", ha="center", va="bottom", fontsize=7)
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([textwrap.fill(d, 13) + f"\n(n={n})" for d, n in zip(c["domain"], c["cases"])],
                           fontsize=7.5, rotation=0)
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------- report

def build_report(comp, universe, ins) -> str:
    big = comp[comp["cases"] >= SMALL_DOMAIN_CASES]
    small = comp[comp["cases"] < SMALL_DOMAIN_CASES]
    total_unique = len(universe)
    total_member = int(comp["cases"].sum())
    L = []
    L.append("# Results summary (auto-generated draft)\n")
    L.append(f"Generated {datetime.date.today().isoformat()} by "
             "`analysis/financial_crime_analysis/compare_domains.py` from `output/tables/`. "
             "Every number below is computed; the wording is a draft to review and edit. "
             "Re-run after any pipeline change.\n")

    L.append("## 1. Scope\n")
    L.append(f"- {total_unique:,} Supreme Court judgments (1950-2025) were classified into at least one "
             f"of {len(comp)} domains. A judgment can belong to more than one domain, so the per-domain "
             f"counts add up to {total_member:,}.")
    L.append("- Influence and citation counts use only citations **between these judgments**. "
             "Citations from the other ~22,000 judgments in the dataset are not counted.")
    L.append("- Domain assignment is rule-based (statute sections + keywords + context terms), not "
             "hand-labelled. In manual spot-checks of 20 judgments per domain, four domains had no clear "
             "errors; Digital Financial Fraud had 6 of 20 clear errors before the final gate fix, and "
             "the corrected Digital corpus has not been fully audited.\n")

    L.append("## 2. Domain comparison\n")
    headers = ["Domain", "Cases", "Citations received per case (95% CI)", "% of cases cited",
               "Own-domain citation rate vs chance (95% CI)", "Median citation lag, yrs (95% CI)",
               "Median year"]
    rows = []
    for _, r in comp.sort_values("cases", ascending=False).iterrows():
        rows.append([r["domain"], f"{int(r['cases']):,}",
                     ("0 (none observed)" if r["mean_citations_same_domain"] == 0 else
                      fmt_ci(r["mean_citations_same_domain"], r["same_domain_ci_low"], r["same_domain_ci_high"], 3)),
                     f"{r['pct_cited_same_domain']:.1f}%",
                     fmt_ci(r["insularity_ratio"], r["ratio_ci_low"], r["ratio_ci_high"], 2),
                     fmt_ci(r["median_citation_lag_years"], r["lag_ci_low"], r["lag_ci_high"], 0),
                     f"{r['median_year']:.0f}"])
    L.append(md_table(headers, rows) + "\n")
    L.append("Own-domain citation rate vs chance: 1.0 means the domain cites its own cases exactly as often "
             "as random choice among older cases would predict; above 1 means it prefers its own domain.\n")

    L.append("## 3. What the data shows\n")
    ranked = big.dropna(subset=["insularity_ratio"]).sort_values("insularity_ratio", ascending=False)
    if len(big):
        lg, sm = big.sort_values("cases").iloc[-1], big.sort_values("cases").iloc[0]
        L.append(f"- **Size.** {lg['domain']} is the largest domain ({int(lg['cases']):,} cases); the "
                 f"smallest ranked domain is {sm['domain']} ({int(sm['cases']):,}).")
        cs = big.sort_values("pct_cited_same_domain")
        L.append(f"- **How often cases are cited.** Between {cs.iloc[0]['pct_cited_same_domain']:.1f}% "
                 f"({cs.iloc[0]['domain']}) and {cs.iloc[-1]['pct_cited_same_domain']:.1f}% "
                 f"({cs.iloc[-1]['domain']}) of cases are cited at least once by another case in the same "
                 "domain. This raw figure favours larger domains; see the next point.")
    if len(ranked) >= 2:
        hi, lo = ranked.iloc[0], ranked.iloc[-1]
        overlap = not (lo["ratio_ci_high"] < hi["ratio_ci_low"])
        L.append("- **Own-domain citation, adjusted for size and era.** "
                 + "; ".join(f"{r['domain']} {r['insularity_ratio']:.2f}" for _, r in ranked.iterrows())
                 + f". Highest: {hi['domain']}; lowest: {lo['domain']}. "
                 + ("Their intervals overlap, so the data do not show a clear difference between them."
                    if overlap else
                    "Their intervals do not overlap, so this difference is unlikely to be chance."))
    lag = big.dropna(subset=["median_citation_lag_years"])
    if len(lag):
        a, b = lag.sort_values("median_citation_lag_years").iloc[[0, -1]].to_dict("records")
        L.append(f"- **Age of the precedent relied on.** The median gap between a case and the case it "
                 f"cites is {a['median_citation_lag_years']:.0f} years ({a['domain']}) to "
                 f"{b['median_citation_lag_years']:.0f} years ({b['domain']}); check the intervals in "
                 "the table before calling any difference real.")
    if len(big):
        out = big.dropna(subset=["pct_outside_the_five_domains"]).sort_values("pct_outside_the_five_domains")
        L.append(f"- **Reliance on precedent outside the five domains.** {out.iloc[0]['pct_outside_the_five_domains']:.0f}% "
                 f"({out.iloc[0]['domain']}) to {out.iloc[-1]['pct_outside_the_five_domains']:.0f}% "
                 f"({out.iloc[-1]['domain']}) of each domain's resolved citations point to judgments that "
                 "belong to none of the five domains (e.g. general criminal-procedure or constitutional rulings).")
    for _, s in small.iterrows():
        i = ins[ins["domain"] == s["domain"]]
        extra = ""
        if len(i) and i.iloc[0]["resolved_citation_links"]:
            r0 = i.iloc[0]
            if bool(r0["expected_too_small"]):
                extra += (f" Own-domain rate vs chance is not reported: {int(r0['observed_own_domain'])} "
                          f"observed against only {r0['expected_own_domain']:.1f} expected by chance, "
                          "too few for a ratio to mean anything.")
            extra += (f" Of its {int(r0['resolved_citation_links'])} resolved citation links, "
                     f"{r0['pct_to_own_domain']:.0f}% go to its own domain, {r0['pct_to_other_domains']:.0f}% "
                     f"to the other four, {r0['pct_outside_the_five_domains']:.0f}% outside the five.")
        L.append(f"- **{s['domain']}** has only {int(s['cases'])} cases and "
                 f"{int(s['internal_citation_links'])} citation links among them, so it is described but "
                 f"not ranked or tested.{extra}")
    L.append("")

    L.append("## 4. Hypothesis check\n")
    L.append("**Stated hypothesis:** the domain built on the oldest law (Financial Fraud) shows a denser, "
             "older citation network than the domain built on the newest law (Digital Financial Fraud).\n")
    fd = comp[comp["domain"] == "Financial Fraud"]
    dd = comp[comp["domain"] == "Digital Financial Fraud"]
    if len(dd) and (dd.iloc[0]["cases"] < SMALL_DOMAIN_CASES or dd.iloc[0]["internal_citation_links"] == 0):
        d0 = dd.iloc[0]
        L.append(f"**Not testable with this data.** Digital Financial Fraud has {int(d0['cases'])} cases and "
                 f"{int(d0['internal_citation_links'])} internal citation links. A network with no internal "
                 "links cannot be called less dense in any meaningful sense - the comparison is undefined, "
                 "not a result. Two explanations are possible and this analysis does not separate them: "
                 "either few Supreme Court judgments on digital financial fraud exist in this corpus up "
                 "to 2025, or the classification rules capture only part of them. (The rules were "
                 "tightened after spot-checks found false positives, which shrank the domain; the "
                 "corrected corpus has not been fully audited.)")
        if len(fd):
            f0 = fd.iloc[0]
            L.append(f"\nFor context, Financial Fraud has {int(f0['cases'])} cases, "
                     f"{int(f0['internal_citation_links'])} internal links, a median citation lag of "
                     f"{f0['median_citation_lag_years']:.0f} years and a median judgment year of "
                     f"{f0['median_year']:.0f}.")
    elif len(fd) and len(dd):
        f0, d0 = fd.iloc[0], dd.iloc[0]
        sep = f0["same_domain_ci_low"] > d0["same_domain_ci_high"]
        L.append(f"Financial Fraud averages {f0['mean_citations_same_domain']:.3f} same-domain citations per "
                 f"case and Digital Financial Fraud {d0['mean_citations_same_domain']:.3f}; the intervals "
                 + ("do not overlap, which supports the 'denser' half of the hypothesis."
                    if sep else "overlap, so the data do not support a clear difference."))
    L.append("\n**What can be said instead.** With five domains and different statutes underneath each, "
             "there are too few points to test a trend against statute age. The comparison that the data "
             "can support is the descriptive one in section 3: how each domain cites within itself, "
             "across domains, and outside the five.\n")

    L.append("## 5. Limitations\n")
    for t in [
        "Only citations between the five domain corpora are counted; influence is therefore measured "
        "within these domains, not across the whole Supreme Court record.",
        "Older cases have had longer to be cited; raw citation counts favour them. The temporal tables "
        "(Phase 3) and the era adjustment in the own-domain rate partly address this.",
        "The own-domain rate assumes a citation could have landed on any older case in the five domains "
        "with equal probability. Real citing is not random (subject matter, court bench), so the "
        "'expected' figure is a baseline, not a model of citing behaviour.",
        ("Most" if comp["pct_cited_same_domain"].max() < 50 else "Many")
        + " cases in every domain are never cited by another case in the study (see % cited). "
        "That is a property of the data, not a calculation error.",
        "Citations are matched by their printed reporter reference (AIR/SCC/SCR). Citations to "
        "cases that are not in the dataset, or in formats the extractor does not recognise, are "
        "unresolved and excluded.",
    ]:
        L.append(f"- {t}")
    L.append("\n## 6. How to reproduce\n")
    L.append("```\npython network/network_analysis/analyze_networks.py\n"
             "python analysis/case_analysis/analyze_cases.py\n"
             "python analysis/citation_analysis/analyze_citations.py\n"
             "python analysis/financial_crime_analysis/compare_domains.py\n```\n")
    return "\n".join(L)


def main():
    for d in (OUTPUT_TABLES, OUTPUT_VISUALIZATIONS, OUTPUT_REPORTS):
        os.makedirs(d, exist_ok=True)

    nm = load_node_metrics()
    per_domain, combined = split_node_metrics(nm)
    netm = pd.read_csv(require(table_path("network_metrics_by_domain.csv"),
                               "run network/network_analysis/analyze_networks.py"))
    avg = pd.read_csv(require(table_path("average_citations_per_case.csv"),
                              "run analysis/citation_analysis/analyze_citations.py"))
    ages = pd.read_csv(require(table_path("domain_age_profile.csv"),
                               "run analysis/case_analysis/analyze_cases.py"))
    top = pd.read_csv(require(table_path("top_cases_by_domain.csv"),
                              "run analysis/case_analysis/analyze_cases.py"))

    universe = build_universe(combined)
    domains = get_domains()
    share = EligibleShare(universe, domains)
    year_map = dict(zip(universe["file_name"], universe["year"]))

    ins_rows = []
    for d in domains:
        path = os.path.join(EDGES_DIR, f"{domain_to_filename(d)}_edges_all.csv")
        r = insularity(d, share, year_map, path)
        if r is None:
            print(f"Skipping {d} - edges file not found: {path}")
        else:
            ins_rows.append(r)
    if not ins_rows:
        sys.exit("No *_edges_all.csv files found in network/citation_network/")
    ins = pd.DataFrame(ins_rows)
    ins.round(4).to_csv(os.path.join(OUTPUT_TABLES, "insularity_by_domain.csv"), index=False)
    print("Saved output/tables/insularity_by_domain.csv")

    comp = build_comparison(netm, avg, ages, top, ins)
    comp.round(4).to_csv(os.path.join(OUTPUT_TABLES, "domain_comparison.csv"), index=False)
    print("Saved output/tables/domain_comparison.csv")

    plot_comparison(comp, os.path.join(OUTPUT_VISUALIZATIONS, "domain_comparison.png"))
    print("Saved output/visualizations/domain_comparison.png")

    report = build_report(comp, universe, ins)
    rp = os.path.join(OUTPUT_REPORTS, "results_summary.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved {rp}\n")
    print(ins[["domain", "links_inside_five_domains", "observed_own_domain",
               "expected_own_domain", "insularity_ratio", "ratio_ci_low",
               "ratio_ci_high", "expected_too_small"]].round(2).to_string(index=False))
    print("\n(expected_too_small = True: ratio is not meaningful and is left blank in the comparison)")


if __name__ == "__main__":
    main()
