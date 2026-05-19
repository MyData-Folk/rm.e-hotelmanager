from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.models.models import RatePlanRule, RatePlanRuleStep
from app.services.rule_engine import calculate_plan_from_rule
from app.services.rules_importer import import_rate_plan_rules_csv


router = APIRouter(
    prefix="/admin/rules",
    tags=["admin-rules"],
    dependencies=[Depends(require_admin_api_key)],
)


class RuleUpdate(BaseModel):
    base_source: Optional[str] = None
    enabled: Optional[bool] = None
    rounding_mode: Optional[str] = None
    rounding_increment: Optional[float] = None
    rounding_scope: Optional[str] = None
    priority: Optional[int] = None


class StepCreate(BaseModel):
    step_order: int
    operation: str
    value: float


class StepUpdate(BaseModel):
    step_order: Optional[int] = None
    operation: Optional[str] = None
    value: Optional[float] = None


class RuleTestPayload(BaseModel):
    hotel_id: str
    plan_code: str
    base_price: float
    rounding_mode: Optional[str] = None
    rounding_increment: Optional[float] = None


def serialize_rule(rule: RatePlanRule, steps: list[RatePlanRuleStep]) -> dict:
    return {
        "id": rule.id,
        "hotel_id": rule.hotel_id,
        "plan_code": rule.plan_code,
        "base_source": rule.base_source,
        "enabled": rule.enabled,
        "rounding_mode": rule.rounding_mode,
        "rounding_increment": rule.rounding_increment,
        "rounding_scope": rule.rounding_scope,
        "priority": rule.priority,
        "steps": [
            {
                "id": step.id,
                "step_order": step.step_order,
                "operation": step.operation,
                "value": step.value,
            }
            for step in sorted(steps, key=lambda item: item.step_order)
        ],
    }


@router.get("/rate-plans")
def list_rate_plan_rules(
    hotel_id: str,
    session: Session = Depends(get_session),
):
    rules = session.exec(
        select(RatePlanRule)
        .where(RatePlanRule.hotel_id == hotel_id)
        .order_by(RatePlanRule.plan_code)
    ).all()

    output = []

    for rule in rules:
        steps = session.exec(
            select(RatePlanRuleStep).where(RatePlanRuleStep.rule_id == rule.id)
        ).all()
        output.append(serialize_rule(rule, steps))

    return output


@router.get("/rate-plans/{rule_id}")
def get_rate_plan_rule(
    rule_id: int,
    session: Session = Depends(get_session),
):
    rule = session.get(RatePlanRule, rule_id)

    if not rule:
        raise HTTPException(status_code=404, detail="Règle introuvable.")

    steps = session.exec(
        select(RatePlanRuleStep).where(RatePlanRuleStep.rule_id == rule.id)
    ).all()

    return serialize_rule(rule, steps)


@router.put("/rate-plans/{rule_id}")
def update_rate_plan_rule(
    rule_id: int,
    payload: RuleUpdate,
    session: Session = Depends(get_session),
):
    rule = session.get(RatePlanRule, rule_id)

    if not rule:
        raise HTTPException(status_code=404, detail="Règle introuvable.")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)

    session.add(rule)
    session.commit()
    session.refresh(rule)

    steps = session.exec(
        select(RatePlanRuleStep).where(RatePlanRuleStep.rule_id == rule.id)
    ).all()

    return serialize_rule(rule, steps)


@router.delete("/rate-plans/{rule_id}")
def delete_rate_plan_rule(
    rule_id: int,
    session: Session = Depends(get_session),
):
    rule = session.get(RatePlanRule, rule_id)

    if not rule:
        raise HTTPException(status_code=404, detail="Règle introuvable.")

    steps = session.exec(
        select(RatePlanRuleStep).where(RatePlanRuleStep.rule_id == rule.id)
    ).all()

    for step in steps:
        session.delete(step)

    session.delete(rule)
    session.commit()

    return {"deleted": True, "rule_id": rule_id}


@router.post("/rate-plans/{rule_id}/steps")
def create_rule_step(
    rule_id: int,
    payload: StepCreate,
    session: Session = Depends(get_session),
):
    rule = session.get(RatePlanRule, rule_id)

    if not rule:
        raise HTTPException(status_code=404, detail="Règle introuvable.")

    step = RatePlanRuleStep(
        rule_id=rule_id,
        step_order=payload.step_order,
        operation=payload.operation,
        value=payload.value,
    )

    session.add(step)
    session.commit()
    session.refresh(step)

    return step


@router.put("/rate-plan-steps/{step_id}")
def update_rule_step(
    step_id: int,
    payload: StepUpdate,
    session: Session = Depends(get_session),
):
    step = session.get(RatePlanRuleStep, step_id)

    if not step:
        raise HTTPException(status_code=404, detail="Étape introuvable.")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(step, key, value)

    session.add(step)
    session.commit()
    session.refresh(step)

    return step


@router.delete("/rate-plan-steps/{step_id}")
def delete_rule_step(
    step_id: int,
    session: Session = Depends(get_session),
):
    step = session.get(RatePlanRuleStep, step_id)

    if not step:
        raise HTTPException(status_code=404, detail="Étape introuvable.")

    session.delete(step)
    session.commit()

    return {"deleted": True, "step_id": step_id}


@router.post("/rate-plans/import-csv")
async def import_rules_csv(
    hotel_id: str = Form(...),
    default_rounding_mode: str = Form("two_decimals"),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un CSV.")

    content = await file.read()

    try:
        return import_rate_plan_rules_csv(
            session=session,
            hotel_id=hotel_id,
            csv_bytes=content,
            default_rounding_mode=default_rounding_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rate-plans/test")
def test_rate_plan_rule(
    payload: RuleTestPayload,
    session: Session = Depends(get_session),
):
    rule = session.exec(
        select(RatePlanRule).where(
            RatePlanRule.hotel_id == payload.hotel_id,
            RatePlanRule.plan_code == payload.plan_code,
            RatePlanRule.enabled == True,
        )
    ).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Aucune règle active pour ce plan.")

    if payload.rounding_mode:
        rule.rounding_mode = payload.rounding_mode

    if payload.rounding_increment is not None:
        rule.rounding_increment = payload.rounding_increment

    steps = session.exec(
        select(RatePlanRuleStep).where(RatePlanRuleStep.rule_id == rule.id)
    ).all()

    result = calculate_plan_from_rule(payload.base_price, rule, steps)

    return {
        "hotel_id": payload.hotel_id,
        "plan_code": payload.plan_code,
        "base_price": payload.base_price,
        "base_source": rule.base_source,
        "rounding_mode": rule.rounding_mode,
        "rounding_increment": rule.rounding_increment,
        **result,
    }
