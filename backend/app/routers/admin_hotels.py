from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.models.models import Hotel, HotelRateSettings


router = APIRouter(
    prefix='/admin',
    tags=['admin'],
    dependencies=[Depends(require_admin_api_key)],
)


class HotelCreate(BaseModel):
    hotel_id: str
    name: str
    timezone: str = 'Europe/Paris'
    currency: str = 'EUR'


class RateSettingsUpdate(BaseModel):
    default_reference_plan_code: Optional[str] = None
    default_reference_room_name: Optional[str] = None
    travco_reference_plan_code: Optional[str] = None
    default_source_mode: Optional[str] = None
    default_rounding_mode: Optional[str] = None
    default_rounding_increment: Optional[float] = None


@router.get('/health')
def admin_health():
    return {'status': 'ok', 'admin': True}


@router.post('/hotels')
def create_hotel(payload: HotelCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(Hotel).where(Hotel.hotel_id == payload.hotel_id)).first()
    if existing:
        raise HTTPException(status_code=409, detail='Hotel already exists')

    hotel = Hotel(
        hotel_id=payload.hotel_id,
        name=payload.name,
        timezone=payload.timezone,
        currency=payload.currency,
    )
    session.add(hotel)

    settings = HotelRateSettings(hotel_id=payload.hotel_id)
    session.add(settings)

    session.commit()
    session.refresh(hotel)

    return hotel


@router.get('/hotels')
def list_hotels(session: Session = Depends(get_session)):
    return session.exec(select(Hotel)).all()


@router.get('/hotels/{hotel_id}')
def get_hotel(hotel_id: str, session: Session = Depends(get_session)):
    hotel = session.exec(select(Hotel).where(Hotel.hotel_id == hotel_id)).first()
    if not hotel:
        raise HTTPException(status_code=404, detail='Hotel not found')
    return hotel


@router.get('/hotels/{hotel_id}/rate-settings')
def get_rate_settings(hotel_id: str, session: Session = Depends(get_session)):
    settings = session.exec(
        select(HotelRateSettings).where(HotelRateSettings.hotel_id == hotel_id)
    ).first()
    if not settings:
        settings = HotelRateSettings(hotel_id=hotel_id)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


@router.put('/hotels/{hotel_id}/rate-settings')
def update_rate_settings(
    hotel_id: str,
    payload: RateSettingsUpdate,
    session: Session = Depends(get_session),
):
    settings = session.exec(
        select(HotelRateSettings).where(HotelRateSettings.hotel_id == hotel_id)
    ).first()
    if not settings:
        settings = HotelRateSettings(hotel_id=hotel_id)
        session.add(settings)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)

    settings.updated_at = datetime.now(timezone.utc)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings
