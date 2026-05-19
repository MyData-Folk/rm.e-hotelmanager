from sqlmodel import Session, SQLModel, create_engine

from app.models.models import AvailabilityCell, HotelConfig
from app.services.availability_exporter import build_availability_json_export


def make_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_build_availability_json_export_uses_config_room_order_and_all_dates():
    with make_session() as session:
        session.add(
            HotelConfig(
                hotel_id="folkestone",
                config_json={
                    "displayOrder": {
                        "rooms": [
                            "Twin Classique",
                            "Double Classique",
                            "Double Deluxe",
                        ]
                    }
                },
            )
        )
        session.add(
            AvailabilityCell(
                hotel_id="folkestone",
                import_id="import-1",
                date="2026-06-01",
                room_name="Double Classique",
                raw_value="x",
                available_quantity=None,
                status="not_available_for_sale",
                label="Non disponible \u00e0 la vente",
            )
        )
        session.add(
            AvailabilityCell(
                hotel_id="folkestone",
                import_id="import-1",
                date="2026-06-02",
                room_name="Twin Classique",
                raw_value="4",
                available_quantity=4,
                status="available",
                label="4 chambre(s) en vente",
            )
        )
        session.commit()

        payload = build_availability_json_export(
            session=session,
            hotel_id="folkestone",
            start="2026-06-01",
            end="2026-06-03",
        )

    assert payload["hotel_id"] == "folkestone"
    assert payload["source"] == "excel"
    assert payload["date_range"] == {
        "start": "2026-06-01",
        "end": "2026-06-03",
    }
    assert [room["room_name"] for room in payload["rooms"]] == [
        "Twin Classique",
        "Double Classique",
        "Double Deluxe",
    ]
    assert [entry["date"] for entry in payload["rooms"][0]["dates"]] == [
        "2026-06-01",
        "2026-06-02",
        "2026-06-03",
    ]
    assert payload["rooms"][0]["dates"][0]["status"] == "unknown"
    assert payload["rooms"][0]["dates"][1]["available_quantity"] == 4
    assert payload["rooms"][1]["dates"][0]["status"] == "not_available_for_sale"
    assert payload["summary"] == {
        "rooms_count": 3,
        "dates_count": 3,
        "available_cells": 1,
        "sold_out_cells": 0,
        "not_available_for_sale_cells": 1,
        "unknown_cells": 7,
        "out_of_range_cells": 0,
        "total_available_quantity": 4,
    }


def test_build_availability_json_export_rejects_invalid_date_range():
    with make_session() as session:
        try:
            build_availability_json_export(
                session=session,
                hotel_id="folkestone",
                start="2026-06-03",
                end="2026-06-01",
            )
        except ValueError as exc:
            assert "date de d\u00e9but" in str(exc)
        else:
            raise AssertionError("Expected invalid date range to raise ValueError")
