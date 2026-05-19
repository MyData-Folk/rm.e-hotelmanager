import re
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.models import (
    HotelConfig,
    Partner,
    PartnerRatePlan,
    RatePlanCatalog,
)


REFERENCE_HINTS = [
    "OTA-RO-FLEX",
    "RACK-RO-FLEX",
    "BAR-RO-FLEX",
    "RO-FLEX",
    "FLEX-RO",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def extract_external_id(partner_name: str) -> str | None:
    match = re.search(r"\((\d+)\)\s*$", partner_name or "")
    if not match:
        return None
    return match.group(1)


def normalize_plan_code(plan_code: str) -> str:
    return str(plan_code or "").strip()


def extract_partners_and_plans(config_json: dict[str, Any]) -> dict[str, Any]:
    partners = config_json.get("partners", {})
    if not isinstance(partners, dict):
        raise ValueError("Le JSON doit contenir un objet 'partners'.")

    extracted_partners = []
    all_plan_codes = set()

    for partner_name, partner_payload in partners.items():
        if not isinstance(partner_payload, dict):
            continue

        codes = partner_payload.get("codes", [])
        if not isinstance(codes, list):
            codes = []

        normalized_codes = [
            normalize_plan_code(code)
            for code in codes
            if normalize_plan_code(code)
        ]

        for code in normalized_codes:
            all_plan_codes.add(code)

        default_discount = partner_payload.get("defaultDiscount") or {}
        if not isinstance(default_discount, dict):
            default_discount = {}

        extracted_partners.append(
            {
                "name": partner_name,
                "external_id": extract_external_id(partner_name),
                "commission": float(partner_payload.get("commission") or 0),
                "default_discount_percentage": default_discount.get("percentage"),
                "codes": normalized_codes,
            }
        )

    return {
        "partners": extracted_partners,
        "plan_codes": sorted(all_plan_codes),
    }


def suggest_reference_plans(plan_codes: list[str]) -> list[str]:
    upper_map = {code.upper(): code for code in plan_codes}
    suggestions = []

    for hint in REFERENCE_HINTS:
        for upper_code, original in upper_map.items():
            if hint in upper_code and original not in suggestions:
                suggestions.append(original)

    if not suggestions:
        for code in plan_codes:
            upper = code.upper()
            if "RO" in upper and "FLEX" in upper:
                suggestions.append(code)

    return suggestions[:10]


def analyze_config_for_hotel(
    session: Session,
    hotel_id: str,
    config_json: dict[str, Any],
) -> dict[str, Any]:
    extracted = extract_partners_and_plans(config_json)
    detected_plan_codes = extracted["plan_codes"]

    existing_catalog_items = session.exec(
        select(RatePlanCatalog).where(RatePlanCatalog.hotel_id == hotel_id)
    ).all()

    known_codes = {item.plan_code for item in existing_catalog_items}
    new_codes = [code for code in detected_plan_codes if code not in known_codes]

    return {
        "hotel_id": hotel_id,
        "partners_count": len(extracted["partners"]),
        "plans_detected": len(detected_plan_codes),
        "known_plans": sorted(list(known_codes.intersection(detected_plan_codes))),
        "new_plans": new_codes,
        "pending_configuration": len(new_codes),
        "reference_suggestions": suggest_reference_plans(detected_plan_codes),
        "partners": extracted["partners"],
    }


def upsert_hotel_config(
    session: Session,
    hotel_id: str,
    config_json: dict[str, Any],
) -> HotelConfig:
    existing = session.exec(
        select(HotelConfig).where(HotelConfig.hotel_id == hotel_id)
    ).first()

    if existing:
        existing.config_json = config_json
        existing.updated_at = utc_now()
        session.add(existing)
        return existing

    config = HotelConfig(
        hotel_id=hotel_id,
        config_json=config_json,
        source="json_upload",
    )
    session.add(config)
    return config


def upsert_partner(
    session: Session,
    hotel_id: str,
    partner_payload: dict[str, Any],
) -> Partner:
    existing = session.exec(
        select(Partner).where(
            Partner.hotel_id == hotel_id,
            Partner.name == partner_payload["name"],
        )
    ).first()

    if existing:
        existing.external_id = partner_payload.get("external_id")
        existing.commission = float(partner_payload.get("commission") or 0)
        existing.default_discount_percentage = partner_payload.get("default_discount_percentage")
        existing.updated_at = utc_now()
        session.add(existing)
        return existing

    partner = Partner(
        hotel_id=hotel_id,
        name=partner_payload["name"],
        external_id=partner_payload.get("external_id"),
        commission=float(partner_payload.get("commission") or 0),
        default_discount_percentage=partner_payload.get("default_discount_percentage"),
        config_source="json_upload",
    )
    session.add(partner)
    session.flush()
    return partner


def replace_partner_rate_plans(
    session: Session,
    hotel_id: str,
    partner: Partner,
    plan_codes: list[str],
) -> None:
    existing_links = session.exec(
        select(PartnerRatePlan).where(
            PartnerRatePlan.hotel_id == hotel_id,
            PartnerRatePlan.partner_id == partner.id,
        )
    ).all()

    for link in existing_links:
        session.delete(link)

    session.flush()

    for plan_code in plan_codes:
        session.add(
            PartnerRatePlan(
                hotel_id=hotel_id,
                partner_id=partner.id,
                plan_code=plan_code,
            )
        )


def ensure_catalog_plan(
    session: Session,
    hotel_id: str,
    plan_code: str,
    created_from: str = "json_upload",
) -> tuple[RatePlanCatalog, bool]:
    existing = session.exec(
        select(RatePlanCatalog).where(
            RatePlanCatalog.hotel_id == hotel_id,
            RatePlanCatalog.plan_code == plan_code,
        )
    ).first()

    if existing:
        return existing, False

    item = RatePlanCatalog(
        hotel_id=hotel_id,
        plan_code=plan_code,
        display_name=plan_code,
        status="pending_configuration",
        is_reference=False,
        created_from=created_from,
    )
    session.add(item)
    return item, True


def import_partner_config(
    session: Session,
    hotel_id: str,
    config_json: dict[str, Any],
) -> dict[str, Any]:
    analysis_before = analyze_config_for_hotel(session, hotel_id, config_json)
    extracted = extract_partners_and_plans(config_json)

    upsert_hotel_config(session, hotel_id, config_json)

    for partner_payload in extracted["partners"]:
        partner = upsert_partner(session, hotel_id, partner_payload)
        replace_partner_rate_plans(
            session=session,
            hotel_id=hotel_id,
            partner=partner,
            plan_codes=partner_payload["codes"],
        )

    new_plans = []
    for plan_code in extracted["plan_codes"]:
        _, created = ensure_catalog_plan(session, hotel_id, plan_code)
        if created:
            new_plans.append(plan_code)

    session.commit()

    return {
        "message": "Configuration partenaires importée",
        "hotel_id": hotel_id,
        "partners_count": len(extracted["partners"]),
        "plans_detected": len(extracted["plan_codes"]),
        "known_plans": analysis_before["known_plans"],
        "new_plans": new_plans,
        "pending_configuration": len(new_plans),
        "reference_suggestions": suggest_reference_plans(extracted["plan_codes"]),
        "next_action": "configure_new_rate_plans" if new_plans else "none",
    }
