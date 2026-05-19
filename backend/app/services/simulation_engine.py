from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.models import AvailabilityCell, HotelConfig, Partner, PartnerRatePlan
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


def normalize_plan_code(plan_code: str | None) -> str | None:
    if not plan_code:
        return None

    value = str(plan_code).strip()
    if " - " in value:
        value = value.split(" - ", 1)[0].strip()

    return value or None


def get_partner_config_payload(
    session: Session,
    hotel_id: str,
    partner_name: str,
) -> dict[str, Any]:
    config = session.exec(
        select(HotelConfig).where(HotelConfig.hotel_id == hotel_id)
    ).first()
    if not config or not isinstance(config.config_json, dict):
        return {}

    partners = config.config_json.get("partners", {})
    if not isinstance(partners, dict):
        return {}

    payload = partners.get(partner_name)
    return payload if isinstance(payload, dict) else {}


def get_partner_discount_config(
    session: Session,
    hotel_id: str,
    partner: Partner,
) -> dict[str, Any]:
    payload = get_partner_config_payload(session, hotel_id, partner.name)
    discount_config = payload.get("defaultDiscount", {})
    if not isinstance(discount_config, dict):
        discount_config = {}

    return {
        "percentage": discount_config.get(
            "percentage",
            partner.default_discount_percentage,
        ),
        "exclude_plans_containing": [
            str(value)
            for value in discount_config.get("excludePlansContaining", [])
            if str(value or "").strip()
        ],
    }


def get_availability_cell(
    session: Session,
    hotel_id: str,
    date: str,
    room_name: str,
) -> AvailabilityCell | None:
    return session.exec(
        select(AvailabilityCell)
        .where(
            AvailabilityCell.hotel_id == hotel_id,
            AvailabilityCell.date == date,
            AvailabilityCell.room_name == room_name,
        )
        .order_by(AvailabilityCell.id.desc())
    ).first()


def parse_iso_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Date invalide: {value}. Format attendu: YYYY-MM-DD.") from exc


def iter_night_dates(start: str, end: str) -> list[str]:
    start_date = parse_iso_date(start)
    end_date = parse_iso_date(end)
    if start_date >= end_date:
        raise ValueError("La date de debut doit etre avant la date de fin.")

    days_count = (end_date - start_date).days
    return [
        (start_date + timedelta(days=offset)).date().isoformat()
        for offset in range(days_count)
    ]


def date_display(value: str) -> str:
    day = parse_iso_date(value).date()
    weekdays = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
    return f"{weekdays[day.weekday()]} {day.strftime('%d/%m')}"


def calculate_commercial_values(
    public_price: float,
    commission_percentage: float = 0,
    partner_discount_percentage: float | None = None,
    promo_discount_percentage: float | None = None,
) -> dict[str, float]:
    partner_discount_rate = float(partner_discount_percentage or 0) / 100
    promo_discount_rate = float(promo_discount_percentage or 0) / 100
    commission_rate = float(commission_percentage or 0) / 100

    price_after_partner_discount = public_price * (1 - partner_discount_rate)
    price_after_promo = price_after_partner_discount * (1 - promo_discount_rate)
    commission_amount = price_after_promo * commission_rate
    net_revenue = price_after_promo - commission_amount

    return {
        "public_price": round(public_price, 2),
        "discount_percentage": float(partner_discount_percentage or 0),
        "partner_discount_percentage": float(partner_discount_percentage or 0),
        "partner_discount_amount": round(
            public_price - price_after_partner_discount,
            2,
        ),
        "promo_discount_percentage": float(promo_discount_percentage or 0),
        "promo_discount_amount": round(
            price_after_partner_discount - price_after_promo,
            2,
        ),
        "discount_amount": round(public_price - price_after_promo, 2),
        "price_after_discount": round(price_after_promo, 2),
        "price_after_partner_discount": round(price_after_partner_discount, 2),
        "price_after_promo": round(price_after_promo, 2),
        "commission_percentage": float(commission_percentage or 0),
        "commission_amount": round(commission_amount, 2),
        "net_revenue": round(net_revenue, 2),
    }


def should_apply_partner_discount(
    plan_code: str,
    apply_partner_discount: bool,
    exclude_plans_containing: list[str],
) -> bool:
    if not apply_partner_discount:
        return False

    normalized_plan = plan_code.lower()
    return not any(keyword.lower() in normalized_plan for keyword in exclude_plans_containing)


def summarize_offers(offers: list[dict[str, Any]]) -> dict[str, Any]:
    available_offers = [offer for offer in offers if not offer["missing"]]
    return {
        "plans_requested": len(offers),
        "plans_simulated": len(offers),
        "available_offers": len(available_offers),
        "missing_rates": len(offers) - len(available_offers),
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
    start: str | None = None,
    end: str | None = None,
    apply_commission: bool = True,
    apply_partner_discount: bool = True,
    promo_discount: float = 0,
) -> dict[str, Any]:
    partner = get_partner(session, hotel_id, partner_name)
    partner_plan_codes = get_partner_plan_codes(session, hotel_id, partner.id)
    requested_plan_code = normalize_plan_code(plan_code)

    if requested_plan_code:
        selected_plan_codes = [requested_plan_code]
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

    discount_config = get_partner_discount_config(session, hotel_id, partner)
    effective_partner_discount = (
        discount_percentage
        if discount_percentage is not None
        else discount_config["percentage"]
    )
    exclude_plans_containing = discount_config["exclude_plans_containing"]
    effective_commission = partner.commission if apply_commission else 0
    simulation_dates = (
        iter_night_dates(start, end)
        if start and end
        else [date]
    )

    offers = []
    daily_results = []

    for code in allowed_plan_codes:
        plan_applies_partner_discount = should_apply_partner_discount(
            plan_code=code,
            apply_partner_discount=apply_partner_discount,
            exclude_plans_containing=exclude_plans_containing,
        )
        plan_partner_discount = (
            effective_partner_discount if plan_applies_partner_discount else 0
        )
        plan_daily_results = []

        for day in simulation_dates:
            resolved = resolve_rate(
                session=session,
                hotel_id=hotel_id,
                date=day,
                room_name=room_name,
                plan_code=code,
                source_mode=source_mode,
            )
            availability_cell = get_availability_cell(session, hotel_id, day, room_name)

            if resolved["missing"]:
                item = {
                    "date": day,
                    "date_display": date_display(day),
                    "plan_code": code,
                    "missing": True,
                    "gross_price": None,
                    "stock": (
                        availability_cell.available_quantity
                        if availability_cell is not None
                        else None
                    ),
                    "availability": (
                        availability_cell.label
                        if availability_cell is not None
                        else "Indisponible"
                    ),
                    "source_used": resolved["source_used"],
                    "source_mode": resolved["source_mode"],
                    "reason": "rate_missing",
                }
                plan_daily_results.append(item)
                daily_results.append(item)
                continue

            commercial = calculate_commercial_values(
                public_price=resolved["price"],
                commission_percentage=effective_commission,
                partner_discount_percentage=plan_partner_discount,
                promo_discount_percentage=promo_discount,
            )
            stock = (
                availability_cell.available_quantity
                if availability_cell is not None
                else None
            )
            item = {
                "date": day,
                "date_display": date_display(day),
                "plan_code": code,
                "missing": False,
                "gross_price": commercial["public_price"],
                "price_after_partner_discount": commercial[
                    "price_after_partner_discount"
                ],
                "price_after_promo": commercial["price_after_promo"],
                "commission": commercial["commission_amount"],
                "net_price": commercial["net_revenue"],
                "stock": stock,
                "availability": "Disponible" if stock and stock > 0 else "Complet",
                "source_used": resolved["source_used"],
                "source_mode": resolved["source_mode"],
                **commercial,
            }
            plan_daily_results.append(item)
            daily_results.append(item)

        valid_days = [item for item in plan_daily_results if not item["missing"]]
        if not valid_days:
            offers.append(
                {
                    "plan_code": code,
                    "missing": True,
                    "source_used": None,
                    "source_mode": source_mode,
                    "reason": "rate_missing",
                    "daily_results": plan_daily_results,
                }
            )
            continue

        subtotal_brut = round(sum(item["gross_price"] for item in valid_days), 2)
        total_partner_discount = round(
            sum(item["partner_discount_amount"] for item in valid_days),
            2,
        )
        total_promo_discount = round(
            sum(item["promo_discount_amount"] for item in valid_days),
            2,
        )
        total_commission = round(sum(item["commission"] for item in valid_days), 2)
        total_net = round(sum(item["net_price"] for item in valid_days), 2)

        offers.append(
            {
                "plan_code": code,
                "missing": False,
                "source_used": valid_days[0]["source_used"],
                "source_mode": source_mode,
                "public_price": subtotal_brut,
                "discount_percentage": float(plan_partner_discount or 0),
                "partner_discount_percentage": float(plan_partner_discount or 0),
                "promo_discount_percentage": float(promo_discount or 0),
                "discount_amount": round(total_partner_discount + total_promo_discount, 2),
                "price_after_discount": round(
                    subtotal_brut - total_partner_discount - total_promo_discount,
                    2,
                ),
                "commission_percentage": float(effective_commission or 0),
                "commission_amount": total_commission,
                "net_revenue": total_net,
                "partner_discount_excluded": not plan_applies_partner_discount,
                "daily_results": plan_daily_results,
            }
        )

    available_offers = [offer for offer in offers if not offer["missing"]]
    best_offer = (
        max(available_offers, key=lambda offer: offer["net_revenue"])
        if available_offers
        else None
    )

    valid_daily_results = [item for item in daily_results if not item["missing"]]
    summary_totals = {
        "subtotal_brut": round(sum(item["gross_price"] for item in valid_daily_results), 2),
        "total_partner_discount": round(
            sum(item["partner_discount_amount"] for item in valid_daily_results),
            2,
        ),
        "total_promo_discount": round(
            sum(item["promo_discount_amount"] for item in valid_daily_results),
            2,
        ),
        "total_commission": round(sum(item["commission"] for item in valid_daily_results), 2),
        "total_net": round(sum(item["net_price"] for item in valid_daily_results), 2),
    }

    return {
        "hotel_id": hotel_id,
        "date": date,
        "date_range": {
            "start": start or date,
            "end": end or date,
            "dates": simulation_dates,
            "nights": len(simulation_dates),
            "end_is_exclusive": bool(start and end),
        },
        "room_name": room_name,
        "partner": {
            "id": partner.id,
            "name": partner.name,
            "external_id": partner.external_id,
            "commission": partner.commission,
            "default_discount_percentage": partner.default_discount_percentage,
            "exclude_plans_containing": exclude_plans_containing,
        },
        "requested_plan_code": requested_plan_code,
        "associated_plan_codes": partner_plan_codes,
        "excluded_plan_codes": excluded_plan_codes,
        "source_mode": source_mode,
        "discount_percentage": float(effective_partner_discount or 0),
        "apply_commission": apply_commission,
        "apply_partner_discount": apply_partner_discount,
        "promo_discount": float(promo_discount or 0),
        "offers": offers,
        "best_offer": best_offer,
        "results": daily_results,
        "simulation_info": {
            "room": room_name,
            "plan": requested_plan_code,
            "partner": partner_name,
            "partner_commission": float(effective_commission or 0),
            "partner_discount": float(effective_partner_discount or 0),
            "promo_discount": float(promo_discount or 0),
            "apply_partner_discount": apply_partner_discount,
            "start_date": start or date,
            "end_date": end or date,
            "nights": len(simulation_dates),
        },
        "summary": {
            **summarize_offers(offers),
            **summary_totals,
        },
    }

def export_simulation_payload(simulation: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "format": "simulation_export_v1",
        **simulation,
    }
