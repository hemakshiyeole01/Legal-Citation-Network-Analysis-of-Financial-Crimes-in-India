"""Response models. They drive the interactive docs at /docs and keep the JSON shape stable."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CaseSummary(BaseModel):
    file_name: str
    title: str
    decision_date: Optional[str] = None
    year: int
    domains: list[str]
    cited_by_count: int
    cites_count: int
    pagerank: Optional[float] = None
    pagerank_rank: int
    self_citation: bool
    pdf_available: bool


class SnippetPart(BaseModel):
    text: str
    match: bool  # True for the words that matched the search


class SearchHit(CaseSummary):
    snippet: Optional[list[SnippetPart]] = None  # only for full-text searches


class TopCase(CaseSummary):
    rank: int
    in_degree: int
    out_degree: int
    pagerank_x_n: Optional[float] = None


class CaseRef(BaseModel):
    file_name: str
    title: str
    decision_date: Optional[str] = None
    year: Optional[int] = None
    domains: list[str]
    relation: Optional[str] = None  # same_domain | cross_domain | outside_scope
    cited_by_count: Optional[int] = None
    pdf_available: bool


class DomainMetric(BaseModel):
    domain: str
    slug: str
    in_degree: int
    out_degree: int
    pagerank: Optional[float] = None
    pagerank_rank: int
    in_degree_rank: int


class CaseDetail(BaseModel):
    case: CaseSummary
    domain_metrics: list[DomainMetric]
    cites: list[CaseRef]
    cited_by: list[CaseRef]
    cites_outside_scope: list[CaseRef]
    citations_total: int
    citations_unresolved: int
    pdf_url: Optional[str] = None


class SearchResponse(BaseModel):
    query: Optional[str] = None
    domain: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    scope: str
    sort: str
    total: int
    limit: int
    offset: int
    results: list[SearchHit]


class DomainSummary(BaseModel):
    slug: str
    name: str
    color: str
    cases: int
    edges: int
    self_loops: int
    edges_excluding_self_loops: int
    density: Optional[float] = None
    mean_in_degree: Optional[float] = None
    pct_cited_at_least_once: Optional[float] = None
    pct_isolated: Optional[float] = None
    first_year: Optional[int] = None
    median_year: Optional[float] = None
    last_year: Optional[int] = None
    pct_before_1980: Optional[float] = None
    pct_1980_to_1999: Optional[float] = None
    pct_2000_onward: Optional[float] = None
    has_internal_citations: bool
    top_case: Optional[TopCase] = None


class DecadeCount(BaseModel):
    decade: int
    cases: int
    pct: Optional[float] = None


class GraphNode(BaseModel):
    id: str
    label: str
    title: str
    year: Optional[int] = None
    domains: list[str]
    group: str
    in_degree: Optional[int] = None
    out_degree: Optional[int] = None
    pagerank: Optional[float] = None
    value: Optional[float] = None


class GraphEdge(BaseModel):
    source: str
    target: str


class DomainGraph(BaseModel):
    domain: str
    domain_name: str
    color: str
    metric: str
    top_n: int
    total_nodes: int
    total_edges: int
    shown_nodes: int
    shown_edges: int
    message: Optional[str] = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Neighbourhood(BaseModel):
    center: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_cites: int
    total_cited_by: int
    limit: int


class TableInfo(BaseModel):
    name: str
    columns: list[str]
    rows: int


class TablePage(BaseModel):
    name: str
    columns: list[str]
    total_rows: int
    limit: int
    offset: int
    rows: list[dict[str, Any]]
