from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.services.simulation_engine import (
    export_simulation_payload,
    simulate_partner_offer,
)


public_router = APIRouter(tags=["simulation"])
admin_router = APIRouter(
    prefix="/admin",
    tags=["admin-simulation"],
    dependencies=[Depends(require_admin_api_key)],
)


class SimulationPayload(BaseModel):
    hotel_id: str
    date: Optional[str] = None
    room_name: Optional[str] = None
    room: Optional[str] = None
    partner_name: str
    plan_code: Optional[str] = None
    plan: Optional[str] = None
    source_mode: str = "hybrid"
    discount_percentage: Optional[float] = None
    start: Optional[str] = None
    end: Optional[str] = None
    apply_commission: bool = True
    apply_partner_discount: bool = True
    promo_discount: float = 0


def run_simulation(payload: SimulationPayload, session: Session) -> dict:
    room_name = payload.room_name or payload.room
    plan_code = payload.plan_code or payload.plan
    date = payload.date or payload.start

    if not date:
        raise ValueError("Une date ou une date de debut est requise.")
    if not room_name:
        raise ValueError("Une chambre est requise.")

    return simulate_partner_offer(
        session=session,
        hotel_id=payload.hotel_id,
        date=date,
        room_name=room_name,
        partner_name=payload.partner_name,
        plan_code=plan_code,
        source_mode=payload.source_mode,
        discount_percentage=payload.discount_percentage,
        start=payload.start,
        end=payload.end,
        apply_commission=payload.apply_commission,
        apply_partner_discount=payload.apply_partner_discount,
        promo_discount=payload.promo_discount,
    )


@public_router.post("/simulate")
def simulate(
    payload: SimulationPayload,
    session: Session = Depends(get_session),
):
    try:
        return run_simulation(payload, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/simulate")
def admin_simulate(
    payload: SimulationPayload,
    session: Session = Depends(get_session),
):
    try:
        return run_simulation(payload, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@public_router.post("/export/simulation")
def export_simulation(
    payload: SimulationPayload,
    response: Response,
    session: Session = Depends(get_session),
):
    try:
        simulation = export_simulation_payload(run_simulation(payload, session))
        export_date = payload.date or payload.start or "simulation"
        response.headers["Content-Disposition"] = (
            f'attachment; filename="simulation-{payload.hotel_id}-{export_date}.json"'
        )
        return simulation
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
