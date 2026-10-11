from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.deps import check_year_range, domain_or_422, get_store
from src.api.schemas import SearchResponse
from src.utils.data_store import DataStore
from src.utils.fulltext import FullTextError, IndexUnavailable

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse,
            summary="Search judgments by case name, or by the words inside them")
def search(
    request: Request,
    q: Optional[str] = Query(None, max_length=200,
                             description="Words to look for. Every word must match. In full-text mode, "
                                         "put words in \"quotes\" to match an exact phrase."),
    scope: Literal["title", "text"] = Query(
        "title", description="'title' searches case names; 'text' searches the full text of the judgments "
                             "and returns a highlighted snippet for each result"),
    domain: Optional[str] = Query(None, description="Domain slug, e.g. corruption, or 'combined' for all"),
    year_from: Optional[int] = Query(None, ge=1900, le=2100),
    year_to: Optional[int] = Query(None, ge=1900, le=2100),
    sort: Optional[Literal["relevance", "cited_by", "pagerank", "year_desc", "year_asc", "title"]] = None,
    limit: int = Query(20, ge=1),
    offset: int = Query(0, ge=0),
    store: DataStore = Depends(get_store),
):
    check_year_range(year_from, year_to)
    resolved = domain_or_422(domain) if domain else None
    limit = min(limit, request.app.state.settings.max_page_size)
    has_query = bool(q and q.strip())

    if scope == "text":
        if not has_query:
            raise HTTPException(status_code=422, detail="Enter at least one word to search for inside the judgments")
        try:
            total, results = store.search_text(q, resolved, year_from, year_to, sort, limit, offset)
        except FullTextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except IndexUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        effective_sort = sort or "relevance"
    else:
        total, results = store.search(q, resolved, year_from, year_to, sort, limit, offset)
        effective_sort = sort or ("relevance" if has_query else "pagerank")

    return {
        "query": q, "scope": scope, "domain": resolved.slug if resolved else None,
        "year_from": year_from, "year_to": year_to, "sort": effective_sort,
        "total": total, "limit": limit, "offset": offset, "results": results,
    }
