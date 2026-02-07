from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.cases_service import (
    filter_case_items,
    get_case_item,
    list_case_ids,
    list_case_items,
    list_taxonomy,
)
from app.schemas import CaseItem, CaseListResponse, TaxonomyResponse

router = APIRouter(prefix="/api", tags=["cases"])


@router.get("/cases", response_model=CaseListResponse)
def get_cases(
    category: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, description="Free text search"),
) -> CaseListResponse:
    items = filter_case_items(
        list_case_items(),
        category=category,
        severity=severity,
        tag=tag,
        search=q,
    )
    return CaseListResponse(total=len(items), items=items)


@router.get("/cases/taxonomy", response_model=TaxonomyResponse)
def get_case_taxonomy() -> TaxonomyResponse:
    return TaxonomyResponse(**list_taxonomy(list_case_items()))


@router.get("/cases/ids")
def get_case_ids(
    category: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, description="Free text search"),
) -> dict:
    items = filter_case_items(
        list_case_items(),
        category=category,
        severity=severity,
        tag=tag,
        search=q,
    )
    return {"total": len(items), "ids": list_case_ids(items)}


@router.get("/cases/{filename}", response_model=CaseItem)
def get_case(filename: str) -> CaseItem:
    item = get_case_item(filename)
    if not item:
        raise HTTPException(
            status_code=404,
            detail={"message": "Case not found", "filename": filename},
        )
    return item
