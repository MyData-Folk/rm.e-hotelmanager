import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.models import RatePlanCatalog, RatePlanRule, RatePlanRuleStep


ALLOWED_OPERATIONS = {
    "multiplier",
    "offset",
    "fixed",
    "percentage_discount",
    "percentage_markup",
}

DEFAULT_ROUNDING_MODE = "two_decimals"
DEFAULT_ROUNDING_SCOPE = "final"


@dataclass
class ImportSummary:
    rules_imported: int
    steps_imported: int
    errors: list[dict[str, Any]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_operation(value: str | None) -> str | None:
    if value is None:
        return None

    operation = str(value).strip().lower()

    if not operation:
        return None

    aliases = {
        "multiply": "multiplier",
        "mult": "multiplier",
        "x": "multiplier",
        "*": "multiplier",
        "+": "offset",
        "add": "offset",
        "addition": "offset",
        "discount": "percentage_discount",
        "markup": "percentage_markup",
    }

    return aliases.get(operation, operation)


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None

    raw = str(value).strip()

    if not raw:
        return None

    raw = raw.replace(",", ".")

    try:
        return float(raw)
    except ValueError:
        return None


def detect_delimiter(content: str) -> str:
    sample = content[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        return dialect.delimiter
    except csv.Error:
        return ","


def ensure_catalog_item(session: Session, hotel_id: str, plan_code: str) -> None:
    existing = session.exec(
        select(RatePlanCatalog).where(
            RatePlanCatalog.hotel_id == hotel_id,
            RatePlanCatalog.plan_code == plan_code,
        )
    ).first()

    if existing:
        return

    session.add(
        RatePlanCatalog(
            hotel_id=hotel_id,
            plan_code=plan_code,
            display_name=plan_code,
            status="pending_configuration",
            created_from="rules_csv_import",
        )
    )


def upsert_rule(
    session: Session,
    hotel_id: str,
    plan_code: str,
    base_source: str,
    rounding_mode: str = DEFAULT_ROUNDING_MODE,
    rounding_increment: float | None = None,
    rounding_scope: str = DEFAULT_ROUNDING_SCOPE,
) -> RatePlanRule:
    existing = session.exec(
        select(RatePlanRule).where(
            RatePlanRule.hotel_id == hotel_id,
            RatePlanRule.plan_code == plan_code,
        )
    ).first()

    if existing:
        existing.base_source = base_source
        existing.enabled = True
        existing.rounding_mode = rounding_mode
        existing.rounding_increment = rounding_increment
        existing.rounding_scope = rounding_scope
        existing.updated_at = utc_now()
        session.add(existing)
        session.flush()
        return existing

    rule = RatePlanRule(
        hotel_id=hotel_id,
        plan_code=plan_code,
        base_source=base_source,
        enabled=True,
        rounding_mode=rounding_mode,
        rounding_increment=rounding_increment,
        rounding_scope=rounding_scope,
    )
    session.add(rule)
    session.flush()
    return rule


def replace_rule_steps(
    session: Session,
    rule_id: int,
    steps: list[dict[str, Any]],
) -> int:
    existing_steps = session.exec(
        select(RatePlanRuleStep).where(RatePlanRuleStep.rule_id == rule_id)
    ).all()

    for step in existing_steps:
        session.delete(step)

    session.flush()

    for step in steps:
        session.add(
            RatePlanRuleStep(
                rule_id=rule_id,
                step_order=step["step_order"],
                operation=step["operation"],
                value=step["value"],
            )
        )

    return len(steps)


def extract_steps_from_row(row: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    steps = []
    errors = []

    for index in range(1, 6):
        operation = normalize_operation(row.get(f"Step{index}Type"))
        value = parse_float(row.get(f"Step{index}Value"))

        if operation is None and value is None:
            continue

        if operation is None:
            errors.append(f"Step{index}Type manquant")
            continue

        if operation not in ALLOWED_OPERATIONS:
            errors.append(f"Opération inconnue Step{index}Type={operation}")
            continue

        if value is None:
            errors.append(f"Step{index}Value invalide")
            continue

        steps.append(
            {
                "step_order": index,
                "operation": operation,
                "value": value,
            }
        )

    return steps, errors


def import_rate_plan_rules_csv(
    session: Session,
    hotel_id: str,
    csv_bytes: bytes,
    default_rounding_mode: str = DEFAULT_ROUNDING_MODE,
) -> dict[str, Any]:
    try:
        content = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = csv_bytes.decode("latin-1")

    delimiter = detect_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)

    required_columns = {"PlanCode", "BaseSource"}

    if not reader.fieldnames:
        raise ValueError("CSV vide ou invalide.")

    missing_columns = required_columns.difference(set(reader.fieldnames))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes: {', '.join(sorted(missing_columns))}")

    rules_imported = 0
    steps_imported = 0
    errors = []

    for line_number, row in enumerate(reader, start=2):
        plan_code = str(row.get("PlanCode") or "").strip()
        base_source = str(row.get("BaseSource") or "OTA").strip() or "OTA"

        if not plan_code:
            errors.append({"line": line_number, "errors": ["PlanCode manquant"]})
            continue

        steps, row_errors = extract_steps_from_row(row)

        if row_errors:
            errors.append(
                {
                    "line": line_number,
                    "plan_code": plan_code,
                    "errors": row_errors,
                }
            )
            continue

        ensure_catalog_item(session, hotel_id, plan_code)

        rule = upsert_rule(
            session=session,
            hotel_id=hotel_id,
            plan_code=plan_code,
            base_source=base_source,
            rounding_mode=default_rounding_mode,
        )

        steps_count = replace_rule_steps(session, rule.id, steps)

        catalog_item = session.exec(
            select(RatePlanCatalog).where(
                RatePlanCatalog.hotel_id == hotel_id,
                RatePlanCatalog.plan_code == plan_code,
            )
        ).first()

        if catalog_item and catalog_item.status == "pending_configuration":
            catalog_item.status = "active"
            catalog_item.updated_at = utc_now()
            session.add(catalog_item)

        rules_imported += 1
        steps_imported += steps_count

    session.commit()

    return {
        "message": "Règles tarifaires importées",
        "hotel_id": hotel_id,
        "delimiter": delimiter,
        "rules_imported": rules_imported,
        "steps_imported": steps_imported,
        "errors": errors,
    }
