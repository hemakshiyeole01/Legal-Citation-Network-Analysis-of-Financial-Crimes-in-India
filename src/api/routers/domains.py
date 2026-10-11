from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import check_year_range, domain_or_404, get_store
from src.api.schemas import DecadeCount, DomainGraph, DomainSummary, TopCase
from src.utils.data_store import DataStore
from src.utils.domains import ALL_VIEWS

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("", response_model=list[DomainSummary], summary="The five domains plus the combined view, with summary statistics")
def list_domains(store: DataStore = Depends(get_store)):
    return [store.domain_summary(d) for d in ALL_VIEWS]


@router.get("/{domain}", response_model=DomainSummary, summary="Summary statistics for one domain")
def get_domain(domain: str, store: DataStore = Depends(get_store)):
    return store.domain_summary(domain_or_404(domain))


@router.get("/{domain}/top-cases", response_model=list[TopCase], summary="Most influential cases in a domain")
def top_cases(
    domain: str,
    metric: Literal["pagerank", "in_degree"] = "pagerank",
    limit: int = Query(10, ge=1, le=100),
    store: DataStore = Depends(get_store),
):
    return store.top_cases(domain_or_404(domain), metric, limit)


@router.get("/{domain}/decades", response_model=list[DecadeCount], summary="Number of cases per decade")
def decades(domain: str, store: DataStore = Depends(get_store)):
    return store.decade_distribution(domain_or_404(domain))


@router.get("/{domain}/graph", response_model=DomainGraph, summary="Nodes and edges for drawing a domain's citation graph")
def graph(
    request: Request,
    domain: str,
    top_n: int = Query(50, ge=1),
    metric: Literal["pagerank", "in_degree"] = "pagerank",
    year_from: Optional[int] = Query(None, ge=1900, le=2100),
    year_to: Optional[int] = Query(None, ge=1900, le=2100),
    connected_only: bool = True,
    store: DataStore = Depends(get_store),
):
    check_year_range(year_from, year_to)
    cap = request.app.state.settings.max_graph_nodes
    return store.domain_graph(domain_or_404(domain), min(top_n, cap), metric, year_from, year_to, connected_only)
