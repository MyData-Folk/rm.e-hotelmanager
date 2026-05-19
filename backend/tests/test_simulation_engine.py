from sqlmodel import Session, SQLModel, create_engine

from app.models.models import (
    AvailabilityCell,
    DerivedRate,
    HotelConfig,
    ImportedRate,
    Partner,
    PartnerRatePlan,
)
from app.services.simulation_engine import (
    export_simulation_payload,
    simulate_partner_offer,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def seed_partner(session: Session):
    partner = Partner(
        hotel_id="folkestone",
        name="Booking",
        external_id="123",
        commission=15,
        default_discount_percentage=10,
    )
    session.add(partner)
    session.flush()
    session.add(
        PartnerRatePlan(
            hotel_id="folkestone",
            partner_id=partner.id,
            plan_code="CWT-BB-FLEX",
        )
    )
    session.add(
        PartnerRatePlan(
            hotel_id="folkestone",
            partner_id=partner.id,
            plan_code="OTA-RO-FLEX",
        )
    )
    session.commit()
    return partner


def test_simulate_partner_offer_applies_discount_and_commission_on_calculated_rate():
    with make_session() as session:
        seed_partner(session)
        session.add(
            DerivedRate(
                hotel_id="folkestone",
                date="2026-06-01",
                room_name="Double Classique",
                plan_code="CWT-BB-FLEX",
                price=200,
            )
        )
        session.commit()

        result = simulate_partner_offer(
            session=session,
            hotel_id="folkestone",
            date="2026-06-01",
            room_name="Double Classique",
            partner_name="Booking",
            plan_code="CWT-BB-FLEX",
            source_mode="hybrid",
        )

    offer = result["offers"][0]
    assert offer["public_price"] == 200
    assert offer["discount_amount"] == 20
    assert offer["price_after_discount"] == 180
    assert offer["commission_amount"] == 27
    assert offer["net_revenue"] == 153
    assert offer["source_used"] == "calculated"
    assert result["best_offer"]["plan_code"] == "CWT-BB-FLEX"


def test_simulate_partner_offer_falls_back_to_excel_rate_in_hybrid_mode():
    with make_session() as session:
        seed_partner(session)
        session.add(
            ImportedRate(
                hotel_id="folkestone",
                import_id="import-1",
                date="2026-06-02",
                room_name="Double Classique",
                plan_code="CWT-BB-FLEX",
                price=180,
                raw_value="180",
            )
        )
        session.commit()

        result = simulate_partner_offer(
            session=session,
            hotel_id="folkestone",
            date="2026-06-02",
            room_name="Double Classique",
            partner_name="Booking",
            plan_code="CWT-BB-FLEX",
            source_mode="hybrid",
            discount_percentage=0,
        )

    assert result["offers"][0]["source_used"] == "excel"
    assert result["offers"][0]["net_revenue"] == 153


def test_simulate_partner_offer_rejects_unassociated_plan():
    with make_session() as session:
        seed_partner(session)

        try:
            simulate_partner_offer(
                session=session,
                hotel_id="folkestone",
                date="2026-06-01",
                room_name="Double Classique",
                partner_name="Booking",
                plan_code="DIRECT-RO",
            )
        except ValueError as exc:
            assert "associe" in str(exc)
        else:
            raise AssertionError("Expected unassociated plan to raise ValueError")


def test_simulate_partner_offer_supports_date_range_promo_and_exclusions():
    with make_session() as session:
        seed_partner(session)
        session.add(
            HotelConfig(
                hotel_id="folkestone",
                config_json={
                    "partners": {
                        "Booking": {
                            "defaultDiscount": {
                                "percentage": 10,
                                "excludePlansContaining": ["OTA"],
                            }
                        }
                    }
                },
            )
        )
        for day, price, stock in [
            ("2026-06-01", 200, 3),
            ("2026-06-02", 100, 0),
        ]:
            session.add(
                ImportedRate(
                    hotel_id="folkestone",
                    import_id="import-1",
                    date=day,
                    room_name="Double Classique",
                    plan_code="OTA-RO-FLEX",
                    price=price,
                    raw_value=str(price),
                )
            )
            session.add(
                AvailabilityCell(
                    hotel_id="folkestone",
                    import_id="import-1",
                    date=day,
                    room_name="Double Classique",
                    raw_value=str(stock),
                    available_quantity=stock,
                    status="available" if stock else "sold_out",
                    label="Disponible" if stock else "Complet",
                )
            )
        session.commit()

        result = simulate_partner_offer(
            session=session,
            hotel_id="folkestone",
            date="2026-06-01",
            room_name="Double Classique",
            partner_name="Booking",
            plan_code="OTA-RO-FLEX - OTA RO FLEX",
            source_mode="hybrid",
            start="2026-06-01",
            end="2026-06-03",
            promo_discount=5,
        )

    assert result["date_range"]["dates"] == ["2026-06-01", "2026-06-02"]
    assert result["offers"][0]["partner_discount_excluded"] is True
    assert result["summary"]["subtotal_brut"] == 300
    assert result["summary"]["total_partner_discount"] == 0
    assert result["summary"]["total_promo_discount"] == 15
    assert result["summary"]["total_commission"] == 42.75
    assert result["summary"]["total_net"] == 242.25
    assert result["results"][0]["availability"] == "Disponible"
    assert result["results"][1]["availability"] == "Complet"


def test_export_simulation_payload_adds_metadata():
    payload = export_simulation_payload(
        {
            "hotel_id": "folkestone",
            "offers": [],
        }
    )

    assert payload["format"] == "simulation_export_v1"
    assert payload["generated_at"]
    assert payload["hotel_id"] == "folkestone"
