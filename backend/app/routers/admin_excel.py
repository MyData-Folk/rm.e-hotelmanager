from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.models.models import AvailabilityCell, ImportedRate, ImportMetadata
from app.services.availability_exporter import build_availability_json_export
from app.services.excel_importer import import_excel_file


router = APIRouter(
    prefix="/admin",
    tags=["admin-excel"],
    dependencies=[Depends(require_admin_api_key)],
)


def serialize_import_metadata(item: ImportMetadata) -> dict:
    return {
        "id": item.id,
        "hotel_id": item.hotel_id,
        "import_id": item.import_id,
        "import_type": item.import_type,
        "filename": item.filename,
        "rows_count": item.rows_count,
        "created_at": item.created_at,
        "metadata": item.metadata_json,
    }


@router.post("/upload/excel")
async def upload_excel(
    hotel_id: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un .xlsx.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Le fichier Excel est vide.")

    try:
        return import_excel_file(
            session=session,
            hotel_id=hotel_id,
            filename=file.filename,
            excel_bytes=content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/imports")
def list_imports(
    hotel_id: str,
    session: Session = Depends(get_session),
):
    imports = session.exec(
        select(ImportMetadata)
        .where(ImportMetadata.hotel_id == hotel_id)
        .order_by(ImportMetadata.created_at.desc())
    ).all()

    return [serialize_import_metadata(item) for item in imports]


@router.get("/imports/{import_id}")
def get_import(
    import_id: str,
    session: Session = Depends(get_session),
):
    item = session.exec(
        select(ImportMetadata).where(ImportMetadata.import_id == import_id)
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Import introuvable.")

    return serialize_import_metadata(item)


@router.get("/availability")
def list_availability(
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
            "id": cell.id,
            "hotel_id": cell.hotel_id,
            "import_id": cell.import_id,
            "date": cell.date,
            "room_name": cell.room_name,
            "raw_value": cell.raw_value,
            "available_quantity": cell.available_quantity,
            "status": cell.status,
            "label": cell.label,
        }
        for cell in cells
    ]


@router.get("/imported-rates")
def list_imported_rates(
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
            "id": rate.id,
            "hotel_id": rate.hotel_id,
            "import_id": rate.import_id,
            "date": rate.date,
            "room_name": rate.room_name,
            "plan_code": rate.plan_code,
            "price": rate.price,
            "raw_value": rate.raw_value,
            "source": rate.source,
            "created_at": rate.created_at,
        }
        for rate in rates
    ]


@router.get("/availability/export/json")
def export_availability_json(
    hotel_id: str,
    start: str,
    end: str,
    response: Response,
    session: Session = Depends(get_session),
):
    try:
        response.headers["Content-Disposition"] = (
            f'attachment; filename="availability-{hotel_id}-{start}-{end}.json"'
        )
        return build_availability_json_export(
            session=session,
            hotel_id=hotel_id,
            start=start,
            end=end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
