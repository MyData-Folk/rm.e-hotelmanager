from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session
import json

from app.core.database import get_session
from app.core.security import require_admin_api_key
from app.services.config_importer import analyze_config_for_hotel, import_partner_config


router = APIRouter(
    prefix="/admin",
    tags=["admin-uploads"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.post("/config/analyze")
async def analyze_config(
    hotel_id: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un JSON.")

    try:
        content = await file.read()
        config_json = json.loads(content.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"JSON invalide: {exc}") from exc

    try:
        return analyze_config_for_hotel(session, hotel_id, config_json)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/upload/config")
async def upload_config(
    hotel_id: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un JSON.")

    try:
        content = await file.read()
        config_json = json.loads(content.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"JSON invalide: {exc}") from exc

    try:
        return import_partner_config(session, hotel_id, config_json)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
