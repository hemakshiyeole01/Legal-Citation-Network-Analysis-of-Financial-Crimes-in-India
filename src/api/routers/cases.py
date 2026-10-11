from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from src.api.deps import get_store
from src.api.schemas import CaseDetail, Neighbourhood
from src.utils.data_store import DataStore

router = APIRouter(prefix="/cases", tags=["cases"])


def _resolve(store: DataStore, file_name: str) -> str:
    resolved = store.resolve_file_name(file_name)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"No case named '{file_name}' in the five domain corpora")
    return resolved


@router.get("/{file_name}", response_model=CaseDetail, summary="Case details with citation lists in both directions")
def case_detail(file_name: str, store: DataStore = Depends(get_store)):
    return store.case_detail(_resolve(store, file_name))


@router.get("/{file_name}/neighbourhood", response_model=Neighbourhood, summary="Graph of the cases a judgment cites and is cited by")
def neighbourhood(
    file_name: str,
    limit: int = Query(30, ge=1, le=100, description="Maximum neighbours per direction"),
    include_outside: bool = False,
    store: DataStore = Depends(get_store),
):
    return store.neighbourhood(_resolve(store, file_name), limit, include_outside)


@router.get("/{file_name}/pdf", summary="Original judgment PDF", response_class=FileResponse)
def case_pdf(file_name: str, download: bool = False, store: DataStore = Depends(get_store)):
    resolved = _resolve(store, file_name)  # must be a known case: no user-supplied paths reach the disk
    path = store.pdfs.find(resolved)
    if path is None:
        raise HTTPException(status_code=404, detail="The original PDF is not available on this server")
    return FileResponse(path, media_type="application/pdf", filename=resolved,
                        content_disposition_type="attachment" if download else "inline")
