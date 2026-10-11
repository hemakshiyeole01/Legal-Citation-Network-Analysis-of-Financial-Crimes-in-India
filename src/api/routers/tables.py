"""Read-only access to the CSV tables in output/tables/.

Only files that actually sit in the tables folder can be requested, and the name is
matched against that directory listing, so a request cannot point anywhere else.
"""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request

from src.api.schemas import TableInfo, TablePage

router = APIRouter(prefix="/tables", tags=["tables"])


def _available(request: Request) -> dict[str, "Path"]:  # noqa: F821
    folder = request.app.state.settings.tables_dir
    if not folder.is_dir():
        return {}
    return {p.stem: p for p in sorted(folder.glob("*.csv"))}


@router.get("", response_model=list[TableInfo], summary="List the available result tables")
def list_tables(request: Request):
    out = []
    for name, path in _available(request).items():
        frame = pd.read_csv(path)
        out.append({"name": name, "columns": [str(c) for c in frame.columns], "rows": len(frame)})
    return out


@router.get("/{name}", response_model=TablePage, summary="Rows of one result table (paged)")
def read_table(request: Request, name: str, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    path = _available(request).get(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No table named '{name}'")
    frame = pd.read_csv(path)
    page = frame.iloc[offset: offset + limit].astype(object).where(frame.iloc[offset: offset + limit].notna(), None)
    return {"name": name, "columns": [str(c) for c in frame.columns], "total_rows": len(frame),
            "limit": limit, "offset": offset, "rows": page.to_dict(orient="records")}
