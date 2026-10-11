from __future__ import annotations

from fastapi import HTTPException, Request

from src.utils.data_store import DataStore
from src.utils.domains import Domain, UnknownDomain, resolve_domain


def get_store(request: Request) -> DataStore:
    return request.app.state.store


def domain_or_404(value: str) -> Domain:
    try:
        return resolve_domain(value)
    except UnknownDomain as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def domain_or_422(value: str) -> Domain:
    try:
        return resolve_domain(value)
    except UnknownDomain as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def check_year_range(year_from: int | None, year_to: int | None) -> None:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise HTTPException(status_code=422, detail="year_from must not be later than year_to")
