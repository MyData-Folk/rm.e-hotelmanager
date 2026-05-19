from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.models import (
    BaseRate,
    DerivedRate,
    HotelRateSettings,
    RatePlanRule,
    RatePlanRuleStep,
)
from app.services.pricing_engine import ROOM_RULES, calculate_room_reference_price
from app.services.rate_resolver import compare_sources, iter_dates, resolve_rates_grid
from app.services.rule_engine import calculate_plan_from_rule


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_rate_settings(session: Session, hotel_id: str) -> HotelRateSettings:
    settings = session.exec(
        select(HotelRateSettings).where(HotelRateSettings.hotel_id == hotel_id)
    ).first()

    if settings:
        return settings

    settings = HotelRateSettings(hotel_id=hotel_id)
    session.add(settings)
    session.flush()
    return settings


def get_default_rooms(rooms: list[str] | None = None) -> list[str]:
    if rooms:
        normalized = []
        for room in rooms:
            room_name = str(room or "").strip()
            if room_name and room_name not in normalized:
                normalized.append(room_name)
        if normalized:
            return normalized

    return list(ROOM_RULES.keys())


def get_enabled_rules(
    session: Session,
    hotel_id: str,
    plan_codes: list[str] | None = None,
) -> list[RatePlanRule]:
    statement = select(RatePlanRule).where(
        RatePlanRule.hotel_id == hotel_id,
        RatePlanRule.enabled == True,
    )

    if plan_codes:
        statement = statement.where(RatePlanRule.plan_code.in_(plan_codes))

    return session.exec(statement.order_by(RatePlanRule.priority, RatePlanRule.plan_code)).all()


def get_rule_steps(session: Session, rule_id: int) -> list[RatePlanRuleStep]:
    return session.exec(
        select(RatePlanRuleStep)
        .where(RatePlanRuleStep.rule_id == rule_id)
        .order_by(RatePlanRuleStep.step_order)
    ).all()


def upsert_base_rate(
    session: Session,
    hotel_id: str,
    date: str,
    room_name: str,
    plan_code: str,
    price: float,
    source: str = "admin_ui",
) -> BaseRate:
    base_rate = session.exec(
        select(BaseRate).where(
            BaseRate.hotel_id == hotel_id,
            BaseRate.date == date,
            BaseRate.room_name == room_name,
            BaseRate.plan_code == plan_code,
        )
    ).first()

    if base_rate:
        base_rate.price = price
        base_rate.source = source
        base_rate.updated_at = utc_now()
        session.add(base_rate)
        session.flush()
        return base_rate

    base_rate = BaseRate(
        hotel_id=hotel_id,
        date=date,
        room_name=room_name,
        plan_code=plan_code,
        price=price,
        source=source,
    )
    session.add(base_rate)
    session.flush()
    return base_rate


def upsert_derived_rate(
    session: Session,
    hotel_id: str,
    date: str,
    room_name: str,
    plan_code: str,
    price: float,
    raw_price: float | None = None,
    source: str = "calculated_from_base_rate",
) -> DerivedRate:
    derived_rate = session.exec(
        select(DerivedRate).where(
            DerivedRate.hotel_id == hotel_id,
            DerivedRate.date == date,
            DerivedRate.room_name == room_name,
            DerivedRate.plan_code == plan_code,
        )
    ).first()

    if derived_rate:
        derived_rate.price = price
        derived_rate.raw_price = raw_price
        derived_rate.source = source
        derived_rate.updated_at = utc_now()
        session.add(derived_rate)
        session.flush()
        return derived_rate

    derived_rate = DerivedRate(
        hotel_id=hotel_id,
        date=date,
        room_name=room_name,
        plan_code=plan_code,
        price=price,
        raw_price=raw_price,
        source=source,
    )
    session.add(derived_rate)
    session.flush()
    return derived_rate


def build_rate_calculations(
    session: Session,
    hotel_id: str,
    base_price: float,
    date: str,
    rooms: list[str] | None = None,
    plan_codes: list[str] | None = None,
) -> dict[str, Any]:
    settings = get_rate_settings(session, hotel_id)
    reference_plan_code = settings.default_reference_plan_code
    reference_room_name = settings.default_reference_room_name
    room_names = get_default_rooms(rooms)
    active_rules = get_enabled_rules(session, hotel_id, plan_codes)

    calculations = []

    for room_name in room_names:
        room_reference_price = calculate_room_reference_price(base_price, room_name)
        calculations.append(
            {
                "hotel_id": hotel_id,
                "date": date,
                "room_name": room_name,
                "plan_code": reference_plan_code,
                "price": room_reference_price,
                "raw_price": room_reference_price,
                "source": "reference_room_rule",
                "trace": [
                    {
                        "step": "room_rule",
                        "reference_room_name": reference_room_name,
                        "base_price": base_price,
                        "result": room_reference_price,
                    }
                ],
            }
        )

        for rule in active_rules:
            if rule.plan_code == reference_plan_code:
                continue

            steps = get_rule_steps(session, rule.id)
            result = calculate_plan_from_rule(room_reference_price, rule, steps)
            calculations.append(
                {
                    "hotel_id": hotel_id,
                    "date": date,
                    "room_name": room_name,
                    "plan_code": rule.plan_code,
                    "price": result["rounded_result"],
                    "raw_price": result["raw_result"],
                    "source": "rate_plan_rule",
                    "rule_id": rule.id,
                    "base_source": rule.base_source,
                    "rounding_mode": result["rounding_mode"],
                    "rounding_increment": result["rounding_increment"],
                    "trace": [
                        {
                            "step": "room_rule",
                            "reference_room_name": reference_room_name,
                            "base_price": base_price,
                            "result": room_reference_price,
                        },
                        *result["trace"],
                    ],
                }
            )

    return {
        "hotel_id": hotel_id,
        "date": date,
        "base_price": base_price,
        "reference_plan_code": reference_plan_code,
        "reference_room_name": reference_room_name,
        "rooms_count": len(room_names),
        "rules_count": len(active_rules),
        "calculations": calculations,
    }


def preview_base_rate(
    session: Session,
    hotel_id: str,
    date: str,
    base_price: float,
    rooms: list[str] | None = None,
    plan_codes: list[str] | None = None,
) -> dict[str, Any]:
    return build_rate_calculations(
        session=session,
        hotel_id=hotel_id,
        base_price=base_price,
        date=date,
        rooms=rooms,
        plan_codes=plan_codes,
    )


def save_base_rates_bulk(
    session: Session,
    hotel_id: str,
    rates: list[dict[str, Any]],
    rooms: list[str] | None = None,
    plan_codes: list[str] | None = None,
) -> dict[str, Any]:
    settings = get_rate_settings(session, hotel_id)
    base_rates_saved = 0
    derived_rates_saved = 0
    previews = []

    for item in rates:
        date = item["date"]
        base_price = float(item["base_price"])
        upsert_base_rate(
            session=session,
            hotel_id=hotel_id,
            date=date,
            room_name=settings.default_reference_room_name,
            plan_code=settings.default_reference_plan_code,
            price=base_price,
        )
        base_rates_saved += 1

        preview = build_rate_calculations(
            session=session,
            hotel_id=hotel_id,
            base_price=base_price,
            date=date,
            rooms=rooms,
            plan_codes=plan_codes,
        )
        previews.append(preview)

        for calculation in preview["calculations"]:
            upsert_derived_rate(
                session=session,
                hotel_id=hotel_id,
                date=calculation["date"],
                room_name=calculation["room_name"],
                plan_code=calculation["plan_code"],
                price=calculation["price"],
                raw_price=calculation["raw_price"],
                source=calculation["source"],
            )
            derived_rates_saved += 1

    session.commit()

    return {
        "message": "Tarifs de base sauvegardes et tarifs recalcules",
        "hotel_id": hotel_id,
        "base_rates_saved": base_rates_saved,
        "derived_rates_saved": derived_rates_saved,
        "previews": previews,
    }


def recalculate_from_base_rates(
    session: Session,
    hotel_id: str,
    start: str,
    end: str,
    rooms: list[str] | None = None,
    plan_codes: list[str] | None = None,
) -> dict[str, Any]:
    settings = get_rate_settings(session, hotel_id)
    requested_dates = iter_dates(start, end)
    base_rates = session.exec(
        select(BaseRate).where(
            BaseRate.hotel_id == hotel_id,
            BaseRate.date.in_(requested_dates),
            BaseRate.room_name == settings.default_reference_room_name,
            BaseRate.plan_code == settings.default_reference_plan_code,
        )
    ).all()
    base_rates_by_date = {base_rate.date: base_rate for base_rate in base_rates}

    recalculated_dates = []
    missing_base_dates = []
    derived_rates_saved = 0

    for day in requested_dates:
        base_rate = base_rates_by_date.get(day)
        if not base_rate:
            missing_base_dates.append(day)
            continue

        preview = build_rate_calculations(
            session=session,
            hotel_id=hotel_id,
            base_price=base_rate.price,
            date=day,
            rooms=rooms,
            plan_codes=plan_codes,
        )

        for calculation in preview["calculations"]:
            upsert_derived_rate(
                session=session,
                hotel_id=hotel_id,
                date=calculation["date"],
                room_name=calculation["room_name"],
                plan_code=calculation["plan_code"],
                price=calculation["price"],
                raw_price=calculation["raw_price"],
                source=calculation["source"],
            )
            derived_rates_saved += 1

        recalculated_dates.append(day)

    session.commit()

    return {
        "message": "Tarifs recalcules",
        "hotel_id": hotel_id,
        "date_range": {
            "start": start,
            "end": end,
        },
        "recalculated_dates": recalculated_dates,
        "missing_base_dates": missing_base_dates,
        "derived_rates_saved": derived_rates_saved,
    }


def get_rates_grid(
    session: Session,
    hotel_id: str,
    start: str,
    end: str,
    rooms: list[str],
    plans: list[str],
    source_mode: str = "hybrid",
) -> dict[str, Any]:
    return resolve_rates_grid(
        session=session,
        hotel_id=hotel_id,
        start=start,
        end=end,
        rooms=rooms,
        plans=plans,
        source_mode=source_mode,
    )


def get_rate_conflicts(
    session: Session,
    hotel_id: str,
    start: str,
    end: str,
    rooms: list[str],
    plans: list[str],
) -> dict[str, Any]:
    comparison = compare_sources(
        session=session,
        hotel_id=hotel_id,
        start=start,
        end=end,
        rooms=rooms,
        plans=plans,
    )
    comparison["conflicts"] = [
        item
        for item in comparison["items"]
        if item["difference"] not in (None, 0)
        or item["missing_calculated"]
        or item["missing_excel"]
    ]
    comparison["summary"]["conflicts_count"] = len(comparison["conflicts"])
    return comparison
