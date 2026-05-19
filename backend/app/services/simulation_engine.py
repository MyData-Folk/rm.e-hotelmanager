from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.models import Partner, PartnerRatePlan
from app.services.rate_resolver import resolve_rate


def get_partner(session: Session, hotel_id: str, partner_name: str) -> Partner:
    partner = session.exec(
        select(Partner).where(
            Partner.hotel_id == hotel_id,
            Partner.name == partner_name,
        )
    ).first()

    if not partner:
        raise ValueError("Partenaire introuvable.")

    return partner


def get_partner_plan_codes(session: Session, hotel_id: str, partner_id: int) -> list[str]:
    links = session.exec(
        select(PartnerRatePlan)
        .where(
            PartnerRatePlan.hotel_id == hotel_id,
            PartnerRatePlan.partner_id == partner_id,
        )
        .order_by(PartnerRatePlan.plan_code)
    ).all()

    return [link.plan_code for link in links]


def calculate_commercial_values(
    public_price: float,
    commission_percentage: float = 0,
    discount_percentage: float | None = None,
) -> dict[str, float]:
    discount_rate = float(discount_percentage or 0) / 100
    commission_rate = float(commission_percentage or 0) / 100

    discounted_price = public_price * (1 - discount_rate)
    commission_amount = discounted_price * commission_rate
    net_revenue = discounted_price - commission_amount

    return {
        "public_price": round(public_price, 2),
        "discount_percentage": float(discount_percentage or 0),
        "discount_amount": round(public_price - discounted_price, 2),
        "price_after_discount": round(discounted_price, 2),
        "commission_percentage": float(commission_percentage or 0),
        "commission_amount": round(commission_amount, 2),
        "net_revenue": round(net_revenue, 2),
    }


def simulate_partner_offer(
    session: Session,
    hotel_id: str,
    date: str,
    room_name: str,
    partner_name: str,
    plan_code: str | None = None,
    source_mode: str = "hybrid",
    discount_percentage: float | None = None,
) -> dict[str, Any]:
    partner = get_partner(session, hotel_id, partner_name)
    partner_plan_codes = get_partner_plan_codes(session, hotel_id, partner.id)

    if plan_code:
        selected_plan_codes = [plan_code]
    else:
        selected_plan_codes = partner_plan_codes

    if not selected_plan_codes:
        raise ValueError("Aucun plan tarifaire associe au partenaire.")

    excluded_plan_codes = [
        code
        for code in selected_plan_codes
        if partner_plan_codes and code not in partner_plan_codes
    ]
    allowed_plan_codes = [
        code
        for code in selected_plan_codes
        if not partner_plan_codes or code in partner_plan_codes
    ]

    if not allowed_plan_codes:
        raise ValueError("Le plan demande n'est pas associe au partenaire.")

    effective_discount = (
        discount_percentage
        if discount_percentage is not None
        else partner.default_discount_percentage
    )

    offers = []

    for code in allowed_plan_codes:
        resolved = resolve_rate(
            session=session,
            hotel_id=hotel_id,
            date=date,
            room_name=room_name,
            plan_code=code,
            source_mode=source_mode,
        )

        if resolved["missing"]:
            offers.append(
                {
                    "plan_code": code,
                    "missing": True,
                    "source_used": resolved["source_used"],
                    "source_mode": resolved["source_mode"],
                    "reason": "rate_missing",
                }
            )
            continue

        commercial = calculate_commercial_values(
            public_price=resolved["price"],
            commission_percentage=partner.commission,
            discount_percentage=effective_discount,
        )
        offers.append(
            {
                "plan_code": code,
                "missing": False,
                "source_used": resolved["source_used"],
                "source_mode": resolved["source_mode"],
                **commercial,
            }
        )

    available_offers = [offer for offer in offers if not offer["missing"]]
    best_offer = (
        max(available_offers, key=lambda offer: offer["net_revenue"])
        if available_offers
        else None
    )

    return {
        "hotel_id": hotel_id,
        "date": date,
        "room_name": room_name,
        "partner": {
            "id": partner.id,
            "name": partner.name,
            "external_id": partner.external_id,
            "commission": partner.commission,
            "default_discount_percentage": partner.default_discount_percentage,
        },
        "requested_plan_code": plan_code,
        "associated_plan_codes": partner_plan_codes,
        "excluded_plan_codes": excluded_plan_codes,
        "source_mode": source_mode,
        "discount_percentage": float(effective_discount or 0),
        "offers": offers,
        "best_offer": best_offer,
        "summary": {
            "plans_requested": len(selected_plan_codes),
            "plans_simulated": len(allowed_plan_codes),
            "available_offers": len(available_offers),
            "missing_rates": len(offers) - len(available_offers),
        },
    }


def export_simulation_payload(simulation: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "format": "simulation_export_v1",
        **simulation,
    }
