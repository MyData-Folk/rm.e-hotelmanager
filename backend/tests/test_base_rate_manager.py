from sqlmodel import Session, SQLModel, create_engine, select

from app.models.models import (
    BaseRate,
    DerivedRate,
    ImportedRate,
    RatePlanRule,
    RatePlanRuleStep,
)
from app.services.base_rate_manager import (
    get_rate_conflicts,
    preview_base_rate,
    recalculate_from_base_rates,
    save_base_rates_bulk,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def seed_rule(session: Session):
    rule = RatePlanRule(
        hotel_id="folkestone",
        plan_code="CWT-BB-FLEX",
        base_source="OTA",
        enabled=True,
        rounding_mode="two_decimals",
    )
    session.add(rule)
    session.flush()
    session.add(
        RatePlanRuleStep(
            rule_id=rule.id,
            step_order=1,
            operation="multiplier",
            value=0.95,
        )
    )
    session.add(
        RatePlanRuleStep(
            rule_id=rule.id,
            step_order=2,
            operation="offset",
            value=15,
        )
    )
    session.commit()


def test_preview_base_rate_applies_room_and_plan_rules():
    with make_session() as session:
        seed_rule(session)

        preview = preview_base_rate(
            session=session,
            hotel_id="folkestone",
            date="2026-06-01",
            base_price=200,
            rooms=["Double Classique", "Twin Classique"],
            plan_codes=["CWT-BB-FLEX"],
        )

    prices = {
        (item["room_name"], item["plan_code"]): item["price"]
        for item in preview["calculations"]
    }
    assert prices[("Double Classique", "OTA-RO-FLEX")] == 200
    assert prices[("Twin Classique", "OTA-RO-FLEX")] == 210
    assert prices[("Double Classique", "CWT-BB-FLEX")] == 205
    assert prices[("Twin Classique", "CWT-BB-FLEX")] == 214.5


def test_save_base_rates_bulk_persists_base_and_derived_rates():
    with make_session() as session:
        seed_rule(session)

        result = save_base_rates_bulk(
            session=session,
            hotel_id="folkestone",
            rates=[{"date": "2026-06-01", "base_price": 200}],
            rooms=["Double Classique"],
            plan_codes=["CWT-BB-FLEX"],
        )

        base_rates = session.exec(select(BaseRate)).all()
        derived_rates = session.exec(select(DerivedRate)).all()

    assert result["base_rates_saved"] == 1
    assert result["derived_rates_saved"] == 2
    assert len(base_rates) == 1
    assert base_rates[0].plan_code == "OTA-RO-FLEX"
    assert {
        (rate.room_name, rate.plan_code, rate.price)
        for rate in derived_rates
    } == {
        ("Double Classique", "OTA-RO-FLEX", 200),
        ("Double Classique", "CWT-BB-FLEX", 205),
    }


def test_recalculate_from_existing_base_rates_updates_derived_rates():
    with make_session() as session:
        seed_rule(session)
        save_base_rates_bulk(
            session=session,
            hotel_id="folkestone",
            rates=[{"date": "2026-06-01", "base_price": 200}],
            rooms=["Double Classique"],
            plan_codes=["CWT-BB-FLEX"],
        )
        base_rate = session.exec(select(BaseRate)).one()
        base_rate.price = 220
        session.add(base_rate)
        session.commit()

        result = recalculate_from_base_rates(
            session=session,
            hotel_id="folkestone",
            start="2026-06-01",
            end="2026-06-02",
            rooms=["Double Classique"],
            plan_codes=["CWT-BB-FLEX"],
        )
        cwt_rate = session.exec(
            select(DerivedRate).where(DerivedRate.plan_code == "CWT-BB-FLEX")
        ).one()

    assert result["recalculated_dates"] == ["2026-06-01"]
    assert result["missing_base_dates"] == ["2026-06-02"]
    assert cwt_rate.price == 224


def test_get_rate_conflicts_compares_calculated_and_excel_rates():
    with make_session() as session:
        seed_rule(session)
        save_base_rates_bulk(
            session=session,
            hotel_id="folkestone",
            rates=[{"date": "2026-06-01", "base_price": 200}],
            rooms=["Double Classique"],
            plan_codes=["CWT-BB-FLEX"],
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
        session.commit()

        conflicts = get_rate_conflicts(
            session=session,
            hotel_id="folkestone",
            start="2026-06-01",
            end="2026-06-01",
            rooms=["Double Classique"],
            plans=["CWT-BB-FLEX"],
        )

    assert conflicts["summary"]["conflicts_count"] == 1
    assert conflicts["conflicts"][0]["calculated_price"] == 205
    assert conflicts["conflicts"][0]["excel_price"] == 210
    assert conflicts["conflicts"][0]["difference"] == -5
