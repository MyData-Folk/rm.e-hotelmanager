from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from app.models.models import DerivedRate, ImportedRate


SOURCE_MODES = {"calculated", "excel", "hybrid"}


def validate_source_mode(source_mode: str | None) -> str:
    mode = (source_mode or "hybrid").strip().lower()
    if mode not in SOURCE_MODES:
        raise ValueError(
            f"Mode source invalide: {source_mode}. Modes attendus: calculated, excel, hybrid."
        )
    return mode


def parse_iso_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Date invalide: {value}. Format attendu: YYYY-MM-DD.") from exc


def iter_dates(start: str, end: str) -> list[str]:
    start_date = parse_iso_date(start)
    end_date = parse_iso_date(end)
    if start_date > end_date:
        raise ValueError("La date de debut doit etre avant ou egale a la date de fin.")

    days_count = (end_date - start_date).days
    return [
        (start_date + timedelta(days=offset)).date().isoformat()
        for offset in range(days_count + 1)
    ]


def normalize_string_list(values: list[str] | None) -> list[str]:
    if not values:
        return []

    normalized = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def get_calculated_rate(
    session: Session,
    hotel_id: str,
    date: str,
    room_name: str,
    plan_code: str,
) -> DerivedRate | None:
    return session.exec(
        select(DerivedRate)
        .where(
            DerivedRate.hotel_id == hotel_id,
            DerivedRate.date == date,
            DerivedRate.room_name == room_name,
            DerivedRate.plan_code == plan_code,
        )
        .order_by(DerivedRate.created_at.desc(), DerivedRate.id.desc())
    ).first()


def get_excel_rate(
    session: Session,
    hotel_id: str,
    date: str,
    room_name: str,
    plan_code: str,
) -> ImportedRate | None:
    return session.exec(
        select(ImportedRate)
        .where(
            ImportedRate.hotel_id == hotel_id,
            ImportedRate.date == date,
            ImportedRate.room_name == room_name,
            ImportedRate.plan_code == plan_code,
            ImportedRate.price != None,
        )
        .order_by(ImportedRate.created_at.desc(), ImportedRate.id.desc())
    ).first()


def serialize_resolved_rate(
    hotel_id: str,
    date: str,
    room_name: str,
    plan_code: str,
    source_mode: str,
    source_used: str | None,
    price: float | None,
    rate_id: int | None = None,
) -> dict[str, Any]:
    return {
        "hotel_id": hotel_id,
        "date": date,
        "room_name": room_name,
        "plan_code": plan_code,
        "price": price,
        "source_used": source_used,
        "source_mode": source_mode,
        "missing": price is None,
        "rate_id": rate_id,
    }


def resolve_rate(
    session: Session,
    hotel_id: str,
    date: str,
    room_name: str,
    plan_code: str,
    source_mode: str = "hybrid",
) -> dict[str, Any]:
    mode = validate_source_mode(source_mode)

    calculated_rate = None
    excel_rate = None

    if mode in {"calculated", "hybrid"}:
        calculated_rate = get_calculated_rate(
            session=session,
            hotel_id=hotel_id,
            date=date,
            room_name=room_name,
            plan_code=plan_code,
        )

    if mode in {"excel", "hybrid"} and (mode == "excel" or calculated_rate is None):
        excel_rate = get_excel_rate(
            session=session,
            hotel_id=hotel_id,
            date=date,
            room_name=room_name,
            plan_code=plan_code,
        )

    if calculated_rate is not None:
        return serialize_resolved_rate(
            hotel_id=hotel_id,
            date=date,
            room_name=room_name,
            plan_code=plan_code,
            source_mode=mode,
            source_used="calculated",
            price=calculated_rate.price,
            rate_id=calculated_rate.id,
        )

    if excel_rate is not None:
        return serialize_resolved_rate(
            hotel_id=hotel_id,
            date=date,
            room_name=room_name,
            plan_code=plan_code,
            source_mode=mode,
            source_used="excel",
            price=excel_rate.price,
            rate_id=excel_rate.id,
        )

    return serialize_resolved_rate(
        hotel_id=hotel_id,
        date=date,
        room_name=room_name,
        plan_code=plan_code,
        source_mode=mode,
        source_used=None,
        price=None,
    )


def resolve_rates_grid(
    session: Session,
    hotel_id: str,
    start: str,
    end: str,
    rooms: list[str],
    plans: list[str],
    source_mode: str = "hybrid",
) -> dict[str, Any]:
    mode = validate_source_mode(source_mode)
    requested_dates = iter_dates(start, end)
    room_names = normalize_string_list(rooms)
    plan_codes = normalize_string_list(plans)

    items = []
    missing_count = 0
    source_counts = {
        "calculated": 0,
        "excel": 0,
        "missing": 0,
    }

    for day in requested_dates:
        for room_name in room_names:
            for plan_code in plan_codes:
                resolved = resolve_rate(
                    session=session,
                    hotel_id=hotel_id,
                    date=day,
                    room_name=room_name,
                    plan_code=plan_code,
                    source_mode=mode,
                )
                items.append(resolved)

                if resolved["missing"]:
                    missing_count += 1
                    source_counts["missing"] += 1
                else:
                    source_counts[resolved["source_used"]] += 1

    return {
        "hotel_id": hotel_id,
        "source_mode": mode,
        "date_range": {
            "start": start,
            "end": end,
        },
        "rooms": room_names,
        "plans": plan_codes,
        "items": items,
        "summary": {
            "dates_count": len(requested_dates),
            "rooms_count": len(room_names),
            "plans_count": len(plan_codes),
            "items_count": len(items),
            "missing_count": missing_count,
            "source_counts": source_counts,
        },
    }


def compare_sources(
    session: Session,
    hotel_id: str,
    start: str,
    end: str,
    rooms: list[str],
    plans: list[str],
) -> dict[str, Any]:
    requested_dates = iter_dates(start, end)
    room_names = normalize_string_list(rooms)
    plan_codes = normalize_string_list(plans)
    items = []
    matched_count = 0
    mismatch_count = 0
    missing_calculated_count = 0
    missing_excel_count = 0

    for day in requested_dates:
        for room_name in room_names:
            for plan_code in plan_codes:
                calculated = resolve_rate(
                    session=session,
                    hotel_id=hotel_id,
                    date=day,
                    room_name=room_name,
                    plan_code=plan_code,
                    source_mode="calculated",
                )
                excel = resolve_rate(
                    session=session,
                    hotel_id=hotel_id,
                    date=day,
                    room_name=room_name,
                    plan_code=plan_code,
                    source_mode="excel",
                )

                calculated_price = calculated["price"]
                excel_price = excel["price"]
                difference = (
                    calculated_price - excel_price
                    if calculated_price is not None and excel_price is not None
                    else None
                )

                if calculated_price is None:
                    missing_calculated_count += 1
                if excel_price is None:
                    missing_excel_count += 1
                if difference == 0:
                    matched_count += 1
                elif difference is not None:
                    mismatch_count += 1

                items.append(
                    {
                        "hotel_id": hotel_id,
                        "date": day,
                        "room_name": room_name,
                        "plan_code": plan_code,
                        "calculated_price": calculated_price,
                        "excel_price": excel_price,
                        "difference": difference,
                        "missing_calculated": calculated_price is None,
                        "missing_excel": excel_price is None,
                    }
                )

    return {
        "hotel_id": hotel_id,
        "date_range": {
            "start": start,
            "end": end,
        },
        "rooms": room_names,
        "plans": plan_codes,
        "items": items,
        "summary": {
            "dates_count": len(requested_dates),
            "rooms_count": len(room_names),
            "plans_count": len(plan_codes),
            "items_count": len(items),
            "matched_count": matched_count,
            "mismatch_count": mismatch_count,
            "missing_calculated_count": missing_calculated_count,
            "missing_excel_count": missing_excel_count,
        },
    }
