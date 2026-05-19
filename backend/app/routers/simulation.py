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
    date: str
    room_name: str
    partner_name: str
    plan_code: Optional[str] = None
    source_mode: str = "hybrid"
    discount_percentage: Optional[float] = None


def run_simulation(payload: SimulationPayload, session: Session) -> dict:
    return simulate_partner_offer(
        session=session,
        hotel_id=payload.hotel_id,
        date=payload.date,
        room_name=payload.room_name,
        partner_name=payload.partner_name,
        plan_code=payload.plan_code,
        source_mode=payload.source_mode,
        discount_percentage=payload.discount_percentage,
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
        response.headers["Content-Disposition"] = (
            f'attachment; filename="simulation-{payload.hotel_id}-{payload.date}.json"'
        )
        return simulation
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
