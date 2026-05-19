from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.models import AvailabilityCell, Hotel, ImportedRate, Partner, PartnerRatePlan
from app.services.base_rate_manager import get_rates_grid


router = APIRouter(tags=['public'])


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@router.get('/health')
def health():
    return {
        'status': 'ok',
        'service': 'rm.e-hotelmanager-api',
        'version': '0.1.0',
    }


@router.get('/hotels')
def list_public_hotels(session: Session = Depends(get_session)):
    hotels = session.exec(select(Hotel).where(Hotel.is_active == True)).all()
    return [
        {
            'hotel_id': hotel.hotel_id,
            'name': hotel.name,
            'timezone': hotel.timezone,
            'currency': hotel.currency,
        }
        for hotel in hotels
    ]


@router.get('/partners')
def list_public_partners(
    hotel_id: str,
    session: Session = Depends(get_session),
):
    partners = session.exec(
        select(Partner)
        .where(Partner.hotel_id == hotel_id)
        .order_by(Partner.name)
    ).all()

    plan_links = session.exec(
        select(PartnerRatePlan)
        .where(PartnerRatePlan.hotel_id == hotel_id)
        .order_by(PartnerRatePlan.plan_code)
    ).all()
    plans_by_partner_id: dict[int, list[str]] = {}
    for link in plan_links:
        plans_by_partner_id.setdefault(link.partner_id, []).append(link.plan_code)

    return [
        {
            'id': partner.id,
            'hotel_id': partner.hotel_id,
            'name': partner.name,
            'external_id': partner.external_id,
            'commission': partner.commission,
            'default_discount_percentage': partner.default_discount_percentage,
            'plan_codes': plans_by_partner_id.get(partner.id, []),
        }
        for partner in partners
    ]


@router.get('/availability')
def list_public_availability(
    hotel_id: str,
    start: str,
    end: str,
    session: Session = Depends(get_session),
):
    cells = session.exec(
        select(AvailabilityCell)
        .where(
            AvailabilityCell.hotel_id == hotel_id,
            AvailabilityCell.date >= start,
            AvailabilityCell.date <= end,
        )
        .order_by(AvailabilityCell.date, AvailabilityCell.room_name)
    ).all()

    return [
        {
            'id': cell.id,
            'hotel_id': cell.hotel_id,
            'import_id': cell.import_id,
            'date': cell.date,
            'room_name': cell.room_name,
            'raw_value': cell.raw_value,
            'available_quantity': cell.available_quantity,
            'status': cell.status,
            'label': cell.label,
        }
        for cell in cells
    ]


@router.get('/imported-rates')
def list_public_imported_rates(
    hotel_id: str,
    start: str,
    end: str,
    session: Session = Depends(get_session),
):
    rates = session.exec(
        select(ImportedRate)
        .where(
            ImportedRate.hotel_id == hotel_id,
            ImportedRate.date >= start,
            ImportedRate.date <= end,
        )
        .order_by(ImportedRate.date, ImportedRate.room_name, ImportedRate.plan_code)
    ).all()

    return [
        {
            'id': rate.id,
            'hotel_id': rate.hotel_id,
            'import_id': rate.import_id,
            'date': rate.date,
            'room_name': rate.room_name,
            'plan_code': rate.plan_code,
            'price': rate.price,
            'raw_value': rate.raw_value,
            'source': rate.source,
            'created_at': rate.created_at,
        }
        for rate in rates
    ]


@router.get('/rates/grid')
def public_rates_grid(
    hotel_id: str,
    start: str,
    end: str,
    rooms: str = Query(..., description='Liste CSV de chambres'),
    plans: str = Query(..., description='Liste CSV de plans tarifaires'),
    source_mode: str = 'hybrid',
    session: Session = Depends(get_session),
):
    try:
        return get_rates_grid(
            session=session,
            hotel_id=hotel_id,
            start=start,
            end=end,
            rooms=split_csv(rooms),
            plans=split_csv(plans),
            source_mode=source_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
