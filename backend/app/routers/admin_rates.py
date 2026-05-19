from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.services.base_rate_manager import (
    get_rate_conflicts,
    get_rates_grid,
    preview_base_rate,
    recalculate_from_base_rates,
    save_base_rates_bulk,
)


router = APIRouter(
    prefix="/admin/rates",
    tags=["admin-rates"],
    dependencies=[Depends(require_admin_api_key)],
)


class RatePreviewPayload(BaseModel):
    hotel_id: str
    date: str
    base_price: float
    rooms: Optional[list[str]] = None
    plans: Optional[list[str]] = None


class BaseRateInput(BaseModel):
    date: str
    base_price: float


class BaseRateBulkPayload(BaseModel):
    hotel_id: str
    rates: list[BaseRateInput]
    rooms: Optional[list[str]] = None
    plans: Optional[list[str]] = None


class RecalculatePayload(BaseModel):
    hotel_id: str
    start: str
    end: str
    rooms: Optional[list[str]] = None
    plans: Optional[list[str]] = None


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@router.post("/preview")
def preview_rates(
    payload: RatePreviewPayload,
    session: Session = Depends(get_session),
):
    try:
        return preview_base_rate(
            session=session,
            hotel_id=payload.hotel_id,
            date=payload.date,
            base_price=payload.base_price,
            rooms=payload.rooms,
            plan_codes=payload.plans,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/base/bulk")
def save_base_rates(
    payload: BaseRateBulkPayload,
    session: Session = Depends(get_session),
):
    try:
        return save_base_rates_bulk(
            session=session,
            hotel_id=payload.hotel_id,
            rates=[item.model_dump() for item in payload.rates],
            rooms=payload.rooms,
            plan_codes=payload.plans,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recalculate")
def recalculate_rates(
    payload: RecalculatePayload,
    session: Session = Depends(get_session),
):
    try:
        return recalculate_from_base_rates(
            session=session,
            hotel_id=payload.hotel_id,
            start=payload.start,
            end=payload.end,
            rooms=payload.rooms,
            plan_codes=payload.plans,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/grid")
def rates_grid(
    hotel_id: str,
    start: str,
    end: str,
    rooms: str = Query(..., description="Liste CSV de chambres"),
    plans: str = Query(..., description="Liste CSV de plans tarifaires"),
    source_mode: str = "hybrid",
    session: Session = Depends(get_session),
):
    try:
        return get_rates_grid(
            session=session,
            hotel_id=hotel_id,
            start=start,
            end=end,
            rooms=split_csv(rooms),
            plans=split_csv(plans),
            source_mode=source_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/conflicts")
def rate_conflicts(
    hotel_id: str,
    start: str,
    end: str,
    rooms: str = Query(..., description="Liste CSV de chambres"),
    plans: str = Query(..., description="Liste CSV de plans tarifaires"),
    session: Session = Depends(get_session),
):
    try:
        return get_rate_conflicts(
            session=session,
            hotel_id=hotel_id,
            start=start,
            end=end,
            rooms=split_csv(rooms),
            plans=split_csv(plans),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
