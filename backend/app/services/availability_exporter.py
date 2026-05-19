from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.models import AvailabilityCell, HotelConfig


def normalize_availability_value(value):
    raw = '' if value is None else str(value).strip().lower()

    if raw == 'x':
        return {
            'raw_value': 'x',
            'available_quantity': None,
            'status': 'not_available_for_sale',
            'label': 'Non disponible à la vente',
        }

    if raw == '0':
        return {
            'raw_value': '0',
            'available_quantity': 0,
            'status': 'sold_out',
            'label': 'Stock épuisé',
        }

    try:
        quantity = int(float(raw))
    except ValueError:
        return {
            'raw_value': raw,
            'available_quantity': None,
            'status': 'unknown',
            'label': 'Valeur non reconnue',
        }

    if 1 <= quantity <= 100:
        return {
            'raw_value': str(quantity),
            'available_quantity': quantity,
            'status': 'available',
            'label': f'{quantity} chambre(s) en vente',
        }

    return {
        'raw_value': raw,
        'available_quantity': quantity,
        'status': 'out_of_range',
        'label': 'Valeur hors plage attendue',
    }


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Date invalide: {value}. Format attendu: YYYY-MM-DD.") from exc


def iter_dates(start: str, end: str) -> list[str]:
    start_date = parse_iso_date(start)
    end_date = parse_iso_date(end)

    if start_date > end_date:
        raise ValueError("La date de début doit être antérieure ou égale à la date de fin.")

    days_count = (end_date - start_date).days
    return [
        (start_date + timedelta(days=offset)).isoformat()
        for offset in range(days_count + 1)
    ]


def extract_config_room_order(config_json: dict[str, Any] | None) -> list[str]:
    if not isinstance(config_json, dict):
        return []

    display_order = config_json.get("displayOrder") or config_json.get("display_order")
    if not isinstance(display_order, dict):
        return []

    rooms = display_order.get("rooms")
    if not isinstance(rooms, list):
        return []

    ordered_rooms = []
    for item in rooms:
        if isinstance(item, str):
            room_name = item.strip()
        elif isinstance(item, dict):
            room_name = str(
                item.get("name")
                or item.get("room_name")
                or item.get("roomName")
                or ""
            ).strip()
        else:
            room_name = ""

        if room_name and room_name not in ordered_rooms:
            ordered_rooms.append(room_name)

    return ordered_rooms


def get_room_order(session: Session, hotel_id: str, cells: list[AvailabilityCell]) -> list[str]:
    config = session.exec(
        select(HotelConfig).where(HotelConfig.hotel_id == hotel_id)
    ).first()

    config_rooms = extract_config_room_order(config.config_json if config else None)
    cell_rooms = sorted({cell.room_name for cell in cells if cell.room_name})

    ordered_rooms = list(config_rooms)
    ordered_rooms.extend(room for room in cell_rooms if room not in ordered_rooms)
    return ordered_rooms


def empty_availability_entry(day: str) -> dict[str, Any]:
    normalized = normalize_availability_value(None)
    return {
        "date": day,
        "raw_value": None,
        "available_quantity": None,
        "status": normalized["status"],
        "label": normalized["label"],
    }


def serialize_availability_cell(cell: AvailabilityCell) -> dict[str, Any]:
    return {
        "date": cell.date,
        "raw_value": cell.raw_value,
        "available_quantity": cell.available_quantity,
        "status": cell.status,
        "label": cell.label,
    }


def build_availability_json_export(
    session: Session,
    hotel_id: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    requested_dates = iter_dates(start, end)

    cells = session.exec(
        select(AvailabilityCell)
        .where(
            AvailabilityCell.hotel_id == hotel_id,
            AvailabilityCell.date >= start,
            AvailabilityCell.date <= end,
        )
        .order_by(AvailabilityCell.id)
    ).all()

    rooms = get_room_order(session, hotel_id, cells)
    cells_by_room_date = {
        (cell.room_name, cell.date): cell
        for cell in cells
    }

    summary = {
        "rooms_count": len(rooms),
        "dates_count": len(requested_dates),
        "available_cells": 0,
        "sold_out_cells": 0,
        "not_available_for_sale_cells": 0,
        "unknown_cells": 0,
        "out_of_range_cells": 0,
        "total_available_quantity": 0,
    }

    room_payloads = []

    for room_index, room_name in enumerate(rooms, start=1):
        date_payloads = []

        for day in requested_dates:
            cell = cells_by_room_date.get((room_name, day))
            entry = serialize_availability_cell(cell) if cell else empty_availability_entry(day)
            status = entry["status"]

            if status == "available":
                summary["available_cells"] += 1
                summary["total_available_quantity"] += entry["available_quantity"] or 0
            elif status == "sold_out":
                summary["sold_out_cells"] += 1
            elif status == "not_available_for_sale":
                summary["not_available_for_sale_cells"] += 1
            elif status == "out_of_range":
                summary["out_of_range_cells"] += 1
            else:
                summary["unknown_cells"] += 1

            date_payloads.append(entry)

        room_payloads.append(
            {
                "room_name": room_name,
                "category_order": room_index,
                "dates": date_payloads,
            }
        )

    return {
        "hotel_id": hotel_id,
        "source": "excel",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_range": {
            "start": start,
            "end": end,
        },
        "legend": {
            "x": "not_available_for_sale",
            "0": "sold_out",
            "1-100": "available_quantity",
        },
        "rooms": room_payloads,
        "summary": summary,
    }
