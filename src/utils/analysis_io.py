"""
Shared helpers for the analysis stages (Phases 4-6).

Keeps the three analysis scripts loading the Phase 3 tables the same way and
using the same bootstrap, so numbers agree between them.
"""

import os
import sys

import numpy as np
import pandas as pd

from config.paths import OUTPUT_TABLES, DATA_PROCESSED

# Must match COMBINED_NAME in network/network_analysis/analyze_networks.py
COMBINED_NAME = "Combined (all domains)"


def table_path(name: str) -> str:
    return os.path.join(OUTPUT_TABLES, name)


def require(path: str, hint: str) -> str:
    if not os.path.exists(path):
        sys.exit(f"Missing file: {path}\n  -> {hint}")
    return path


def load_node_metrics() -> pd.DataFrame:
    path = require(table_path("node_metrics.csv"),
                   "run network/network_analysis/analyze_networks.py first")
    return pd.read_csv(path)


def split_node_metrics(nm: pd.DataFrame):
    """(per-domain rows, combined-graph rows)"""
    per_domain = nm[nm["domain"] != COMBINED_NAME].copy()
    combined = nm[nm["domain"] == COMBINED_NAME].copy()
    return per_domain, combined


def add_decade(df: pd.DataFrame, col: str = "year") -> pd.DataFrame:
    df = df.dropna(subset=[col]).copy()
    df[col] = df[col].astype(int)
    df["decade"] = (df[col] // 10) * 10
    return df


def all_judgments_per_decade():
    """Supreme Court judgments per decade in the FULL cleaned corpus - the
    denominator that separates 'the Court decided more cases that decade' from
    'this domain grew'. Returns None if the corpus file isn't there."""
    path = os.path.join(DATA_PROCESSED, "all_judgments_cleaned.csv")
    if not os.path.exists(path):
        return None
    years = pd.read_csv(path, usecols=["year"])["year"]
    years = pd.to_numeric(years, errors="coerce").dropna().astype(int)
    return (years // 10 * 10).value_counts().sort_index()


def bootstrap_ci(values, stat: str = "mean", n_boot: int = 2000, seed: int = 42,
                 alpha: float = 0.05):
    """Percentile bootstrap CI for the mean or median of `values`.
    Returns (low, high); (nan, nan) for empty input."""
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(n_boot, v.size))
    sample = v[idx]
    stats = sample.mean(axis=1) if stat == "mean" else np.median(sample, axis=1)
    lo, hi = np.percentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(lo), float(hi))
