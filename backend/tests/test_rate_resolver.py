from sqlmodel import Session, SQLModel, create_engine

from app.models.models import DerivedRate, ImportedRate
from app.services.rate_resolver import (
    compare_sources,
    resolve_rate,
    resolve_rates_grid,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def seed_rates(session: Session):
    session.add(
        DerivedRate(
            hotel_id="folkestone",
            date="2026-06-01",
            room_name="Double Classique",
            plan_code="CWT-BB-FLEX",
            price=205,
            raw_price=205,
        )
    )
    session.add(
        ImportedRate(
            hotel_id="folkestone",
            import_id="import-1",
            date="2026-06-01",
            room_name="Double Classique",
            plan_code="CWT-BB-FLEX",
            price=210,
            raw_value="210",
        )
    )
    session.add(
        ImportedRate(
            hotel_id="folkestone",
            import_id="import-1",
            date="2026-06-02",
            room_name="Double Classique",
            plan_code="CWT-BB-FLEX",
            price=220,
            raw_value="220",
        )
    )
    session.commit()


def test_resolve_rate_uses_calculated_first_in_hybrid_mode():
    with make_session() as session:
        seed_rates(session)

        resolved = resolve_rate(
            session=session,
            hotel_id="folkestone",
            date="2026-06-01",
            room_name="Double Classique",
            plan_code="CWT-BB-FLEX",
            source_mode="hybrid",
        )

    assert resolved["price"] == 205
    assert resolved["source_used"] == "calculated"
    assert resolved["missing"] is False


def test_resolve_rate_hybrid_falls_back_to_excel():
    with make_session() as session:
        seed_rates(session)

        resolved = resolve_rate(
            session=session,
            hotel_id="folkestone",
            date="2026-06-02",
            room_name="Double Classique",
            plan_code="CWT-BB-FLEX",
            source_mode="hybrid",
        )

    assert resolved["price"] == 220
    assert resolved["source_used"] == "excel"


def test_resolve_rate_respects_source_modes_and_missing_values():
    with make_session() as session:
        seed_rates(session)

        calculated = resolve_rate(
            session=session,
            hotel_id="folkestone",
            date="2026-06-02",
            room_name="Double Classique",
            plan_code="CWT-BB-FLEX",
            source_mode="calculated",
        )
        excel = resolve_rate(
            session=session,
            hotel_id="folkestone",
            date="2026-06-01",
            room_name="Double Classique",
            plan_code="CWT-BB-FLEX",
            source_mode="excel",
        )

    assert calculated["missing"] is True
    assert calculated["price"] is None
    assert excel["price"] == 210
    assert excel["source_used"] == "excel"


def test_resolve_rates_grid_summarizes_sources():
    with make_session() as session:
        seed_rates(session)

        grid = resolve_rates_grid(
            session=session,
            hotel_id="folkestone",
            start="2026-06-01",
            end="2026-06-03",
            rooms=["Double Classique"],
            plans=["CWT-BB-FLEX"],
            source_mode="hybrid",
        )

    assert [item["source_used"] for item in grid["items"]] == [
        "calculated",
        "excel",
        None,
    ]
    assert grid["summary"]["source_counts"] == {
        "calculated": 1,
        "excel": 1,
        "missing": 1,
    }


def test_compare_sources_reports_differences_and_missing_counts():
    with make_session() as session:
        seed_rates(session)

        comparison = compare_sources(
            session=session,
            hotel_id="folkestone",
            start="2026-06-01",
            end="2026-06-02",
            rooms=["Double Classique"],
            plans=["CWT-BB-FLEX"],
        )

    assert comparison["items"][0]["calculated_price"] == 205
    assert comparison["items"][0]["excel_price"] == 210
    assert comparison["items"][0]["difference"] == -5
    assert comparison["items"][1]["missing_calculated"] is True
    assert comparison["summary"]["mismatch_count"] == 1
    assert comparison["summary"]["missing_calculated_count"] == 1
    assert comparison["summary"]["missing_excel_count"] == 0
