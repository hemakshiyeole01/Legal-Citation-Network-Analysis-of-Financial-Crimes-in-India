"""Central place for file paths and API settings.

Nothing else in the project should hard-code a path such as C:\\Users\\...
Every path below is relative to the repository root, and every one of them can
be overridden with an environment variable, so the same code runs on both
teammates' machines, in tests, and on a demo laptop.

Environment variables (all optional):
    LCN_NODE_METRICS   path to node_metrics.csv
    LCN_EDGES_DIR      folder holding the *_edges_all.csv / *_edges_internal.csv files
    LCN_TABLES_DIR     folder holding the output tables (CSV)
    LCN_PDF_DIRS       one or more folders with the original judgment PDFs,
                       separated by the OS path separator (";" on Windows, ":" elsewhere)
    LCN_CORPUS_DIR     folder holding the five *_corpus.csv files (data/final)
    LCN_FTS_DB         where the full-text search index is stored (built by
                       scripts/build_search_index.py)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _path_from_env(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


def _default_pdf_dirs() -> tuple[Path, ...]:
    value = os.environ.get("LCN_PDF_DIRS")
    if value:
        return tuple(Path(p).expanduser() for p in value.split(os.pathsep) if p)
    # 1) a small folder holding only the judgments used in this project (see
    #    scripts/collect_pdfs.py), 2) the full raw Kaggle download, if present.
    return (
        PROJECT_ROOT / "data" / "final" / "pdfs",
        PROJECT_ROOT / "data" / "raw" / "sc_judgments",
    )


@dataclass(frozen=True)
class Settings:
    node_metrics_path: Path = field(
        default_factory=lambda: _path_from_env(
            "LCN_NODE_METRICS", PROJECT_ROOT / "output" / "tables" / "node_metrics.csv"
        )
    )
    edges_dir: Path = field(
        default_factory=lambda: _path_from_env(
            "LCN_EDGES_DIR", PROJECT_ROOT / "network" / "citation_network"
        )
    )
    tables_dir: Path = field(
        default_factory=lambda: _path_from_env(
            "LCN_TABLES_DIR", PROJECT_ROOT / "output" / "tables"
        )
    )
    pdf_dirs: tuple[Path, ...] = field(default_factory=_default_pdf_dirs)
    corpus_dir: Path = field(
        default_factory=lambda: _path_from_env("LCN_CORPUS_DIR", PROJECT_ROOT / "data" / "final")
    )
    fts_db_path: Path = field(
        default_factory=lambda: _path_from_env(
            "LCN_FTS_DB", PROJECT_ROOT / "data" / "index" / "fulltext.db"
        )
    )

    # API behaviour
    api_title: str = "Legal Citation Network API"
    api_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8000
    max_page_size: int = 100
    max_graph_nodes: int = 300

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
