from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.models.models import Partner, PartnerRatePlan, RatePlanCatalog, RatePlanRule


router = APIRouter(
    prefix="/admin/rate-plans",
    tags=["admin-rate-plans"],
    dependencies=[Depends(require_admin_api_key)],
)


class RatePlanCreate(BaseModel):
    hotel_id: str
    plan_code: str
    display_name: Optional[str] = None
    status: str = "pending_configuration"
    is_reference: bool = False
    reference_role: Optional[str] = None


class RatePlanUpdate(BaseModel):
    display_name: Optional[str] = None
    status: Optional[str] = None
    is_reference: Optional[bool] = None
    reference_role: Optional[str] = None


@router.get("/catalog")
def list_catalog(
    hotel_id: str,
    session: Session = Depends(get_session),
):
    items = session.exec(
        select(RatePlanCatalog)
        .where(RatePlanCatalog.hotel_id == hotel_id)
        .order_by(RatePlanCatalog.plan_code)
    ).all()

    output = []

    for item in items:
        partner_links = session.exec(
            select(PartnerRatePlan).where(
                PartnerRatePlan.hotel_id == hotel_id,
                PartnerRatePlan.plan_code == item.plan_code,
            )
        ).all()

        partner_names = []
        for link in partner_links:
            partner = session.get(Partner, link.partner_id)
            if partner:
                partner_names.append(partner.name)

        rule = session.exec(
            select(RatePlanRule).where(
                RatePlanRule.hotel_id == hotel_id,
                RatePlanRule.plan_code == item.plan_code,
                RatePlanRule.enabled == True,
            )
        ).first()

        output.append(
            {
                "id": item.id,
                "hotel_id": item.hotel_id,
                "plan_code": item.plan_code,
                "display_name": item.display_name,
                "status": item.status,
                "is_reference": item.is_reference,
                "reference_role": item.reference_role,
                "created_from": item.created_from,
                "partners": sorted(partner_names),
                "has_active_rule": rule is not None,
            }
        )

    return output


@router.get("/pending")
def list_pending(
    hotel_id: str,
    session: Session = Depends(get_session),
):
    return session.exec(
        select(RatePlanCatalog)
        .where(
            RatePlanCatalog.hotel_id == hotel_id,
            RatePlanCatalog.status == "pending_configuration",
        )
        .order_by(RatePlanCatalog.plan_code)
    ).all()


@router.post("/catalog")
def create_catalog_item(
    payload: RatePlanCreate,
    session: Session = Depends(get_session),
):
    existing = session.exec(
        select(RatePlanCatalog).where(
            RatePlanCatalog.hotel_id == payload.hotel_id,
            RatePlanCatalog.plan_code == payload.plan_code,
        )
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="Ce plan existe déjà pour cet hôtel.")

    item = RatePlanCatalog(
        hotel_id=payload.hotel_id,
        plan_code=payload.plan_code,
        display_name=payload.display_name or payload.plan_code,
        status=payload.status,
        is_reference=payload.is_reference,
        reference_role=payload.reference_role,
        created_from="manual",
    )

    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/catalog/{plan_id}")
def update_catalog_item(
    plan_id: int,
    payload: RatePlanUpdate,
    session: Session = Depends(get_session),
):
    item = session.get(RatePlanCatalog, plan_id)
    if not item:
        raise HTTPException(status_code=404, detail="Plan introuvable.")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.post("/catalog/{plan_id}/disable")
def disable_catalog_item(
    plan_id: int,
    session: Session = Depends(get_session),
):
    item = session.get(RatePlanCatalog, plan_id)
    if not item:
        raise HTTPException(status_code=404, detail="Plan introuvable.")

    item.status = "inactive"
    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.post("/catalog/{plan_id}/ignore")
def ignore_catalog_item(
    plan_id: int,
    session: Session = Depends(get_session),
):
    item = session.get(RatePlanCatalog, plan_id)
    if not item:
        raise HTTPException(status_code=404, detail="Plan introuvable.")

    item.status = "ignored"
    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/catalog/{plan_id}")
def delete_catalog_item(
    plan_id: int,
    session: Session = Depends(get_session),
):
    item = session.get(RatePlanCatalog, plan_id)
    if not item:
        raise HTTPException(status_code=404, detail="Plan introuvable.")

    rule = session.exec(
        select(RatePlanRule).where(
            RatePlanRule.hotel_id == item.hotel_id,
            RatePlanRule.plan_code == item.plan_code,
        )
    ).first()

    partner_link = session.exec(
        select(PartnerRatePlan).where(
            PartnerRatePlan.hotel_id == item.hotel_id,
            PartnerRatePlan.plan_code == item.plan_code,
        )
    ).first()

    if rule or partner_link:
        raise HTTPException(
            status_code=409,
            detail="Ce plan est utilisé. Désactive-le plutôt que de le supprimer.",
        )

    session.delete(item)
    session.commit()
    return {"deleted": True, "plan_id": plan_id}
