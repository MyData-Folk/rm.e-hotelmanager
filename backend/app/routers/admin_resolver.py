from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.services.rate_resolver import (
    compare_sources,
    resolve_rate,
    resolve_rates_grid,
)


router = APIRouter(
    prefix="/admin/rates",
    tags=["admin-rate-resolver"],
    dependencies=[Depends(require_admin_api_key)],
)


class ResolveGridPayload(BaseModel):
    hotel_id: str
    start: str
    end: str
    rooms: list[str]
    plans: list[str]
    source_mode: str = "hybrid"


class CompareSourcesPayload(BaseModel):
    hotel_id: str
    start: str
    end: str
    rooms: list[str]
    plans: list[str]


@router.get("/resolve")
def resolve_single_rate(
    hotel_id: str,
    date: str,
    room_name: str,
    plan_code: str,
    source_mode: str = "hybrid",
    session: Session = Depends(get_session),
):
    try:
        return resolve_rate(
            session=session,
            hotel_id=hotel_id,
            date=date,
            room_name=room_name,
            plan_code=plan_code,
            source_mode=source_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/resolve-grid")
def resolve_grid(
    payload: ResolveGridPayload,
    session: Session = Depends(get_session),
):
    try:
        return resolve_rates_grid(
            session=session,
            hotel_id=payload.hotel_id,
            start=payload.start,
            end=payload.end,
            rooms=payload.rooms,
            plans=payload.plans,
            source_mode=payload.source_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/compare-sources")
def compare_rate_sources(
    payload: CompareSourcesPayload,
    session: Session = Depends(get_session),
):
    try:
        return compare_sources(
            session=session,
            hotel_id=payload.hotel_id,
            start=payload.start,
            end=payload.end,
            rooms=payload.rooms,
            plans=payload.plans,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
