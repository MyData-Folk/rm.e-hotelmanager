from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.models import Hotel


router = APIRouter(tags=['public'])


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
