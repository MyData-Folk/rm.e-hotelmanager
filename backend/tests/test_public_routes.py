from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.database import get_session
from app.models.models import AvailabilityCell, Hotel, ImportedRate, Partner, PartnerRatePlan
from app.routers import public


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            Hotel(
                hotel_id="folkestone",
                name="Folkestone Opera",
            )
        )
        partner = Partner(
            hotel_id="folkestone",
            name="Booking.com (6562)",
            commission=0,
            default_discount_percentage=10,
        )
        session.add(partner)
        session.flush()
        session.add(
            PartnerRatePlan(
                hotel_id="folkestone",
                partner_id=partner.id,
                plan_code="OTA-RO-NANR",
            )
        )
        session.add(
            AvailabilityCell(
                hotel_id="folkestone",
                import_id="import-1",
                date="2026-05-13",
                room_name="Double Classique",
                raw_value="3",
                available_quantity=3,
                status="available",
                label="3 chambre(s) en vente",
            )
        )
        session.add(
            ImportedRate(
                hotel_id="folkestone",
                import_id="import-1",
                date="2026-05-13",
                room_name="Double Classique",
                plan_code="OTA-RO-NANR",
                price=153,
                raw_value="153",
            )
        )
        session.commit()

    app = FastAPI()
    app.include_router(public.router)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def test_public_user_routes_do_not_require_admin_key():
    client = make_client()

    partners = client.get("/partners?hotel_id=folkestone")
    availability = client.get(
        "/availability?hotel_id=folkestone&start=2026-05-13&end=2026-05-13"
    )
    grid = client.get(
        "/rates/grid?hotel_id=folkestone&start=2026-05-13&end=2026-05-13"
        "&rooms=Double%20Classique&plans=OTA-RO-NANR&source_mode=hybrid"
    )

    assert partners.status_code == 200
    assert partners.json()[0]["plan_codes"] == ["OTA-RO-NANR"]
    assert availability.status_code == 200
    assert availability.json()[0]["available_quantity"] == 3
    assert grid.status_code == 200
    assert grid.json()["items"][0]["price"] == 153
    assert grid.json()["items"][0]["source_used"] == "excel"
