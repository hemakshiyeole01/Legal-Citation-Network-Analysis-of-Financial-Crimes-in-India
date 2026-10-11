"""In-memory data layer behind the API.

Loads, once at start-up:
  * output/tables/node_metrics.csv       one row per (domain, case) plus a 'Combined' view
  * network/citation_network/*_edges_*   citation edge lists written by Person A
  * the original judgment PDFs, if they are on this machine (see PdfStore)

Everything the API returns is derived from those files, so the numbers shown in the
interface are the same numbers that are in the report tables.

A note on self-citations
------------------------
The edge lists contain a few rows where a judgment "cites" itself (36 in the current
files, e.g. a case that quotes its own SCC reference). A case cannot cite itself, so
the citation lists and counts exposed here leave those rows out and flag the case
with `self_citation: true`. The per-domain `in_degree` / PageRank values in
node_metrics.csv were computed on the raw edges and are reported as they are.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import pandas as pd

from config.settings import Settings
from src.utils.domains import ALL_VIEWS, COMBINED, DOMAINS, Domain, domain_by_name
from src.utils.formatting import (
    clean_number,
    decade_of,
    normalize_text,
    parse_case_name,
    short_label,
    stem,
)
from src.utils.fulltext import FullTextIndex
from src.utils.pdf_store import PdfStore

log = logging.getLogger(__name__)

REQUIRED_NODE_COLUMNS = {
    "domain", "file_name", "title", "year", "case_domains",
    "in_degree", "out_degree", "pagerank", "pagerank_x_N", "pagerank_rank", "in_degree_rank",
}
EDGE_ALL_COLUMNS = ["citing_file_name", "citing_domain", "cited_citation_normalized",
                    "cited_file_name", "cited_domain", "edge_type"]
SEARCH_SORTS = ("relevance", "cited_by", "pagerank", "year_desc", "year_asc", "title")
GRAPH_METRICS = ("pagerank", "in_degree")


class DataError(RuntimeError):
    """Raised when a required data file is missing or malformed."""


@dataclass(frozen=True)
class Case:
    file_name: str
    parties: str
    decision_date: str | None
    year: int
    domains: tuple[str, ...]
    pagerank: float
    pagerank_x_n: float
    pagerank_rank: int
    in_degree: int
    out_degree: int


class DataStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._load_nodes()
        self._load_edges()
        self.pdfs = PdfStore(settings.pdf_dirs)
        self.fulltext = FullTextIndex(settings.fts_db_path)
        self._build_search_frame()

    # ------------------------------------------------------------------ loading
    def _load_nodes(self) -> None:
        path = self.settings.node_metrics_path
        if not path.is_file():
            raise DataError(f"node_metrics.csv not found at {path}. Set LCN_NODE_METRICS or run Person A's analysis first.")
        nm = pd.read_csv(path)
        missing = REQUIRED_NODE_COLUMNS - set(nm.columns)
        if missing:
            raise DataError(f"{path.name} is missing columns: {sorted(missing)}")
        nm["case_domains"] = nm["case_domains"].fillna("")

        self.domain_frames: dict[str, pd.DataFrame] = {
            d.name: nm[nm["domain"] == d.name].set_index("file_name", drop=False) for d in DOMAINS
        }
        self.combined_frame = nm[nm["domain"] == COMBINED.name].set_index("file_name", drop=False)
        if self.combined_frame.empty:
            raise DataError(f"{path.name} has no '{COMBINED.name}' rows.")

        order = {d.name: i for i, d in enumerate(DOMAINS)}
        self.cases: dict[str, Case] = {}
        for row in self.combined_frame.itertuples(index=False):
            parsed = parse_case_name(row.file_name)
            tags = tuple(sorted((t.strip() for t in str(row.case_domains).split(";") if t.strip()),
                                key=lambda t: order.get(t, 99)))
            self.cases[row.file_name] = Case(
                file_name=row.file_name,
                parties=parsed["parties"] or str(row.title),
                decision_date=parsed["decision_date"],
                year=int(row.year),
                domains=tags,
                pagerank=float(row.pagerank),
                pagerank_x_n=float(row.pagerank_x_N),
                pagerank_rank=int(row.pagerank_rank),
                in_degree=int(row.in_degree),
                out_degree=int(row.out_degree),
            )
        self._lower_names = {fn.lower(): fn for fn in self.cases}

    def _read_edges(self, name: str, **kwargs: Any) -> pd.DataFrame | None:
        path = self.settings.edges_dir / name
        if not path.is_file():
            log.warning("Edge file missing: %s", path)
            return None
        return pd.read_csv(path, dtype=str, keep_default_na=False, **kwargs)

    def _load_edges(self) -> None:
        all_frames = []
        self.domain_edges: dict[str, list[tuple[str, str]]] = {}
        self.domain_edge_rows: dict[str, int] = {}
        self.domain_self_loops: dict[str, int] = {}
        for d in DOMAINS:
            edges_all = self._read_edges(f"{d.edge_prefix}_edges_all.csv")
            if edges_all is not None:
                all_frames.append(edges_all)
            internal = self._read_edges(f"{d.edge_prefix}_edges_internal.csv")
            pairs = [] if internal is None else list(zip(internal["citing_file_name"], internal["cited_file_name"]))
            self.domain_edge_rows[d.name] = len(pairs)
            self.domain_self_loops[d.name] = sum(1 for a, b in pairs if a == b)
            self.domain_edges[d.name] = [(a, b) for a, b in pairs if a != b]

        edges_all = (pd.concat(all_frames, ignore_index=True) if all_frames
                     else pd.DataFrame(columns=EDGE_ALL_COLUMNS))

        # Citation mentions per judgment (a judgment that sits in two domain corpora appears
        # in two edge files, so de-duplicate on the cited string).
        mentions = edges_all.drop_duplicates(["citing_file_name", "cited_citation_normalized"])
        self.citations_total = mentions.groupby("citing_file_name").size().to_dict()
        self.citations_unresolved = (
            mentions[mentions["edge_type"] == "UNRESOLVED"].groupby("citing_file_name").size().to_dict()
        )

        resolved = edges_all[edges_all["cited_file_name"] != ""]
        pairs_df = resolved[["citing_file_name", "cited_file_name"]].drop_duplicates()
        in_scope = pairs_df[pairs_df["citing_file_name"].isin(self.cases) & pairs_df["cited_file_name"].isin(self.cases)]
        self.combined_edges_raw = len(in_scope)
        self.self_citing = set(pairs_df.loc[pairs_df["citing_file_name"] == pairs_df["cited_file_name"], "citing_file_name"])

        self.cites: dict[str, list[str]] = defaultdict(list)
        self.cited_by: dict[str, list[str]] = defaultdict(list)
        self.cites_outside: dict[str, list[str]] = defaultdict(list)
        self.combined_edges: list[tuple[str, str]] = []
        for a, b in zip(pairs_df["citing_file_name"], pairs_df["cited_file_name"]):
            if a == b or a not in self.cases:
                continue
            if b in self.cases:
                self.cites[a].append(b)
                self.cited_by[b].append(a)
                self.combined_edges.append((a, b))
            else:
                self.cites_outside[a].append(b)
        self.domain_edges[COMBINED.name] = self.combined_edges
        self.domain_edge_rows[COMBINED.name] = self.combined_edges_raw
        self.domain_self_loops[COMBINED.name] = self.combined_edges_raw - len(self.combined_edges)

    def _build_search_frame(self) -> None:
        rows = []
        for c in self.cases.values():
            spaced = " ".join(stem(c.file_name).replace("_", " ").split())
            spaced = " ".join(spaced.split(" ")[:-1]) if spaced.split(" ")[-1].isdigit() and len(spaced.split(" ")) > 1 and spaced.split(" ")[-2].isdigit() else spaced
            row = {
                "file_name": c.file_name,
                "search_text": normalize_text(spaced),
                "parties_sort": c.parties.lower(),
                "year": c.year,
                "pagerank": c.pagerank,
                "cited_by": len(self.cited_by.get(c.file_name, ())),
            }
            for d in DOMAINS:
                row[f"in_{d.slug}"] = d.name in c.domains
            rows.append(row)
        self._search_frame = pd.DataFrame(rows)

    # ------------------------------------------------------------------ lookups
    def resolve_file_name(self, file_name: str) -> str | None:
        if file_name in self.cases:
            return file_name
        return self._lower_names.get(file_name.lower())

    def get(self, file_name: str) -> Case | None:
        name = self.resolve_file_name(file_name)
        return self.cases[name] if name else None

    def frame_for(self, domain: Domain) -> pd.DataFrame:
        return self.combined_frame if domain is COMBINED else self.domain_frames[domain.name]

    # ------------------------------------------------------------------ shaping
    def case_summary(self, case: Case) -> dict[str, Any]:
        return {
            "file_name": case.file_name,
            "title": case.parties,
            "decision_date": case.decision_date,
            "year": case.year,
            "domains": list(case.domains),
            "cited_by_count": len(self.cited_by.get(case.file_name, ())),
            "cites_count": len(self.cites.get(case.file_name, ())),
            "pagerank": clean_number(case.pagerank, 6),
            "pagerank_rank": case.pagerank_rank,
            "self_citation": case.file_name in self.self_citing,
            "pdf_available": self.pdfs.has(case.file_name),
        }

    def _case_ref(self, file_name: str, relation: str | None = None) -> dict[str, Any]:
        case = self.cases.get(file_name)
        if case is not None:
            return {
                "file_name": file_name, "title": case.parties, "decision_date": case.decision_date,
                "year": case.year, "domains": list(case.domains), "relation": relation,
                "cited_by_count": len(self.cited_by.get(file_name, ())),
                "pdf_available": self.pdfs.has(file_name),
            }
        parsed = parse_case_name(file_name)
        return {
            "file_name": file_name, "title": parsed["parties"], "decision_date": parsed["decision_date"],
            "year": parsed["year"], "domains": [], "relation": "outside_scope",
            "cited_by_count": None, "pdf_available": self.pdfs.has(file_name),
        }

    def _relation(self, a: Case, b: Case) -> str:
        return "same_domain" if set(a.domains) & set(b.domains) else "cross_domain"

    # ------------------------------------------------------------------ search
    _SORT_ORDERS = {
        "cited_by": (["cited_by", "pagerank"], [False, False]),
        "pagerank": (["pagerank"], [False]),
        "year_desc": (["year", "pagerank"], [False, False]),
        "year_asc": (["year", "pagerank"], [True, False]),
        "title": (["parties_sort"], [True]),
    }

    def _filter_mask(self, df: pd.DataFrame, domain: Domain | None, year_from: int | None,
                     year_to: int | None) -> pd.Series:
        mask = pd.Series(True, index=df.index)
        if domain is not None and domain is not COMBINED:
            mask &= df[f"in_{domain.slug}"]
        if year_from is not None:
            mask &= df["year"] >= year_from
        if year_to is not None:
            mask &= df["year"] <= year_to
        return mask

    def _page(self, view: pd.DataFrame, sort: str, relevance: tuple[list[str], list[bool]],
              limit: int, offset: int) -> tuple[int, list[str]]:
        by, ascending = relevance if sort == "relevance" else self._SORT_ORDERS[sort]
        view = view.sort_values(by=by, ascending=ascending, kind="mergesort")
        return len(view), list(view["file_name"].iloc[offset: offset + limit])

    def search(self, q: str | None = None, domain: Domain | None = None, year_from: int | None = None,
               year_to: int | None = None, sort: str | None = None, limit: int = 20,
               offset: int = 0) -> tuple[int, list[dict[str, Any]]]:
        """Search case names (parties, decision date)."""
        df = self._search_frame
        mask = self._filter_mask(df, domain, year_from, year_to)

        tokens = normalize_text(q).split() if q else []
        score = pd.Series(0.0, index=df.index)
        text = df["search_text"]
        for token in tokens:
            mask &= text.str.contains(token, regex=False)
            # a match at the start of a word beats a match in the middle of one
            score += (text.str.startswith(token) | text.str.contains(" " + token, regex=False)).astype(float)
        if len(tokens) > 1:
            score += 2.0 * text.str.contains(" ".join(tokens), regex=False).astype(float)

        sort = sort or ("relevance" if tokens else "pagerank")
        view = df.assign(_score=score)[mask]
        total, names = self._page(view, sort, (["_score", "pagerank"], [False, False]), limit, offset)
        return total, [self.case_summary(self.cases[fn]) for fn in names]

    def search_text(self, q: str, domain: Domain | None = None, year_from: int | None = None,
                    year_to: int | None = None, sort: str | None = None, limit: int = 20,
                    offset: int = 0) -> tuple[int, list[dict[str, Any]]]:
        """Search inside the judgments. Raises FullTextError (nothing to search for) or
        IndexUnavailable (index not built); the API turns those into 422 and 503."""
        matched = self.fulltext.match(q)  # best match first
        position = {fn: i for i, fn in enumerate(matched)}
        df = self._search_frame
        view = df[df["file_name"].isin(position) & self._filter_mask(df, domain, year_from, year_to)]
        view = view.assign(_text_rank=view["file_name"].map(position))
        total, names = self._page(view, sort or "relevance", (["_text_rank"], [True]), limit, offset)
        snippets = self.fulltext.snippets(q, names)
        results = []
        for fn in names:
            summary = self.case_summary(self.cases[fn])
            summary["snippet"] = snippets.get(fn, [])
            results.append(summary)
        return total, results

    # ------------------------------------------------------------------ cases
    def case_detail(self, file_name: str) -> dict[str, Any] | None:
        case = self.get(file_name)
        if case is None:
            return None
        fn = case.file_name

        def ordered(names: list[str], relation_from_case: bool) -> list[dict[str, Any]]:
            refs = []
            for other in names:
                other_case = self.cases[other]
                relation = self._relation(case, other_case)
                refs.append(self._case_ref(other, relation))
            return sorted(refs, key=lambda r: (-(r["cited_by_count"] or 0), -(r["year"] or 0)))

        domain_metrics = []
        for name in case.domains:
            frame = self.domain_frames.get(name)
            if frame is None or fn not in frame.index:
                continue
            row = frame.loc[fn]
            domain_metrics.append({
                "domain": name, "slug": domain_by_name(name).slug,
                "in_degree": int(row["in_degree"]), "out_degree": int(row["out_degree"]),
                "pagerank": clean_number(row["pagerank"], 6),
                "pagerank_rank": int(row["pagerank_rank"]), "in_degree_rank": int(row["in_degree_rank"]),
            })

        outside = [self._case_ref(o) for o in self.cites_outside.get(fn, ())]
        outside.sort(key=lambda r: -(r["year"] or 0))
        return {
            "case": self.case_summary(case),
            "domain_metrics": domain_metrics,
            "cites": ordered(self.cites.get(fn, []), True),
            "cited_by": ordered(self.cited_by.get(fn, []), False),
            "cites_outside_scope": outside,
            "citations_total": int(self.citations_total.get(fn, 0)),
            "citations_unresolved": int(self.citations_unresolved.get(fn, 0)),
            "pdf_url": f"/cases/{fn}/pdf" if self.pdfs.has(fn) else None,
        }

    # ------------------------------------------------------------------ graphs
    def _graph_node(self, case: Case, group: str, value: float | None = None) -> dict[str, Any]:
        return {
            "id": case.file_name,
            "label": short_label(case.parties),
            "title": case.parties,
            "year": case.year,
            "domains": list(case.domains),
            "group": group,
            "in_degree": case.in_degree,
            "out_degree": case.out_degree,
            "pagerank": clean_number(case.pagerank, 6),
            "value": clean_number(case.pagerank_x_n if value is None else value, 4),
        }

    def _primary_group(self, case: Case) -> str:
        return domain_by_name(case.domains[0]).slug if case.domains else "combined"

    def domain_graph(self, domain: Domain, top_n: int = 50, metric: str = "pagerank",
                     year_from: int | None = None, year_to: int | None = None,
                     connected_only: bool = True) -> dict[str, Any]:
        frame = self.frame_for(domain)
        edges = self.domain_edges.get(domain.name, [])
        connected = {n for edge in edges for n in edge}

        view = frame
        if year_from is not None:
            view = view[view["year"] >= year_from]
        if year_to is not None:
            view = view[view["year"] <= year_to]
        if connected_only:
            view = view[view["file_name"].isin(connected)]
        view = view.sort_values([metric, "pagerank"], ascending=[False, False], kind="mergesort").head(top_n)

        selected = set(view["file_name"])
        nodes = []
        for row in view.itertuples(index=False):
            case = self.cases[row.file_name]
            group = domain.slug if domain is not COMBINED else self._primary_group(case)
            nodes.append(self._graph_node(case, group, value=float(row.pagerank_x_N)))
            # per-domain in/out degree come from that domain's own graph
            nodes[-1]["in_degree"], nodes[-1]["out_degree"] = int(row.in_degree), int(row.out_degree)
        shown_edges = [{"source": a, "target": b} for a, b in edges if a in selected and b in selected]

        message = None
        if not edges:
            message = (f"{domain.name} has no citation links between its own judgments in this dataset, "
                       "so there is no graph to draw.")
        elif not nodes:
            message = "No cases match these filters."
        return {
            "domain": domain.slug, "domain_name": domain.name, "color": domain.color,
            "metric": metric, "top_n": top_n,
            "total_nodes": int(len(frame)), "total_edges": len(edges),
            "shown_nodes": len(nodes), "shown_edges": len(shown_edges),
            "message": message, "nodes": nodes, "edges": shown_edges,
        }

    def neighbourhood(self, file_name: str, limit: int = 30, include_outside: bool = False) -> dict[str, Any] | None:
        case = self.get(file_name)
        if case is None:
            return None
        fn = case.file_name

        def top(names: list[str]) -> list[str]:
            return sorted(names, key=lambda n: -len(self.cited_by.get(n, ())))[:limit]

        ids = {fn} | set(top(self.cites.get(fn, []))) | set(top(self.cited_by.get(fn, [])))
        nodes = [self._graph_node(self.cases[i], self._primary_group(self.cases[i])) for i in ids]
        edges = [{"source": a, "target": b} for a in ids for b in self.cites.get(a, ()) if b in ids]
        if include_outside:
            for other in self.cites_outside.get(fn, [])[:limit]:
                ref = self._case_ref(other)
                nodes.append({"id": other, "label": short_label(ref["title"]), "title": ref["title"],
                              "year": ref["year"], "domains": [], "group": "outside",
                              "in_degree": None, "out_degree": None, "pagerank": None, "value": 0.5})
                edges.append({"source": fn, "target": other})
        return {"center": fn, "nodes": nodes, "edges": edges,
                "total_cites": len(self.cites.get(fn, ())), "total_cited_by": len(self.cited_by.get(fn, ())),
                "limit": limit}

    # ------------------------------------------------------------------ domains
    def top_cases(self, domain: Domain, metric: str = "pagerank", limit: int = 10) -> list[dict[str, Any]]:
        frame = self.frame_for(domain)
        rank_col = "pagerank_rank" if metric == "pagerank" else "in_degree_rank"
        view = frame.sort_values([rank_col, "pagerank"], ascending=[True, False], kind="mergesort").head(limit)
        out = []
        for position, row in enumerate(view.itertuples(index=False), start=1):
            summary = self.case_summary(self.cases[row.file_name])
            summary.update({
                "rank": position,
                "in_degree": int(row.in_degree), "out_degree": int(row.out_degree),
                "pagerank": clean_number(row.pagerank, 6),
                "pagerank_rank": int(row.pagerank_rank),  # rank within this domain's own graph
                "pagerank_x_n": clean_number(row.pagerank_x_N, 4),
            })
            out.append(summary)
        return out

    def domain_summary(self, domain: Domain) -> dict[str, Any]:
        frame = self.frame_for(domain)
        n = int(len(frame))
        edges_raw = self.domain_edge_rows.get(domain.name, 0)
        self_loops = self.domain_self_loops.get(domain.name, 0)
        edges_clean = edges_raw - self_loops
        years = frame["year"]
        isolated = (frame["in_degree"] + frame["out_degree"]) == 0
        top = self.top_cases(domain, "pagerank", 1) if n else []
        return {
            "slug": domain.slug, "name": domain.name, "color": domain.color,
            "cases": n,
            "edges": edges_raw,
            "self_loops": self_loops,
            "edges_excluding_self_loops": edges_clean,
            "density": clean_number(edges_raw / (n * (n - 1)), 6) if n > 1 else None,
            "mean_in_degree": clean_number(frame["in_degree"].mean(), 3) if n else None,
            "pct_cited_at_least_once": clean_number((frame["in_degree"] > 0).mean() * 100, 3) if n else None,
            "pct_isolated": clean_number(isolated.mean() * 100, 3) if n else None,
            "first_year": int(years.min()) if n else None,
            "median_year": clean_number(years.median(), 1) if n else None,
            "last_year": int(years.max()) if n else None,
            "pct_before_1980": clean_number((years < 1980).mean() * 100, 1) if n else None,
            "pct_1980_to_1999": clean_number(((years >= 1980) & (years < 2000)).mean() * 100, 1) if n else None,
            "pct_2000_onward": clean_number((years >= 2000).mean() * 100, 1) if n else None,
            "has_internal_citations": edges_clean > 0,
            "top_case": top[0] if top else None,
        }

    def decade_distribution(self, domain: Domain) -> list[dict[str, Any]]:
        frame = self.frame_for(domain)
        counts = frame["year"].map(decade_of).value_counts().sort_index()
        total = int(counts.sum()) or 1
        return [{"decade": int(dec), "cases": int(c), "pct": clean_number(c / total * 100, 1)}
                for dec, c in counts.items()]

    def overview(self) -> dict[str, Any]:
        return {"cases": len(self.cases), "citation_links": len(self.combined_edges),
                "self_citing_cases": len(self.self_citing), "pdfs_available": len(self.pdfs),
                "fulltext_index": self.fulltext.info(),
                "domains": [d.slug for d in DOMAINS]}
