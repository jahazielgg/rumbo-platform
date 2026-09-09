from uuid import UUID

import fitz
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.infrastructure.settings import get_settings
from app.infrastructure.database import get_db
from app.shared_kernel.errors import NotFoundError, ValidationError

from ..application.services import FloorplanService
from ..domain.entities import Floorplan
from ..infrastructure.repositories import SqlAlchemyFloorplanRepository
from ..infrastructure.storage import LocalFloorplanStorage
from .schemas import FloorplanResponse

router = APIRouter(prefix="/floorplans", tags=["floorplans"])


def get_service(db: Session = Depends(get_db)) -> FloorplanService:
    settings = get_settings()
    return FloorplanService(
        repository=SqlAlchemyFloorplanRepository(db),
        storage=LocalFloorplanStorage(settings.upload_path),
        max_upload_mb=settings.max_upload_mb,
    )


def serialize(entity: Floorplan) -> FloorplanResponse:
    file_url = f"/uploads/{entity.stored_filename}"
    preview_url = f"/api/v1/floorplans/{entity.id}/preview" if entity.media_type == "application/pdf" else file_url
    return FloorplanResponse(
        id=entity.id,
        name=entity.name,
        building_name=entity.building_name,
        floor_label=entity.floor_label,
        original_filename=entity.original_filename,
        media_type=entity.media_type,
        created_at=entity.created_at,
        file_url=file_url,
        preview_url=preview_url,
    )


@router.get("", response_model=list[FloorplanResponse])
def list_floorplans(service: FloorplanService = Depends(get_service)):
    return [serialize(item) for item in service.list()]


@router.get("/{floorplan_id}", response_model=FloorplanResponse)
def get_floorplan(floorplan_id: UUID, service: FloorplanService = Depends(get_service)):
    try:
        return serialize(service.get(floorplan_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{floorplan_id}/preview")
def preview_floorplan(floorplan_id: UUID, service: FloorplanService = Depends(get_service)):
    try:
        entity = service.get(floorplan_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if entity.media_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Este plano no requiere una vista previa rasterizada.")

    path = service.storage.resolve(entity.stored_filename)
    try:
        with fitz.open(path) as document:
            if document.page_count == 0:
                raise HTTPException(status_code=422, detail="El PDF no contiene páginas.")
            page = document.load_page(0)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            content = pixmap.tobytes("png")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="No se pudo renderizar la primera página del PDF.") from exc
    return Response(content=content, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@router.post("", response_model=FloorplanResponse, status_code=status.HTTP_201_CREATED)
async def upload_floorplan(
    name: str = Form(...),
    building_name: str = Form(...),
    floor_label: str = Form(...),
    file: UploadFile = File(...),
    service: FloorplanService = Depends(get_service),
):
    try:
        content = await file.read()
        entity = service.create(
            name=name,
            building_name=building_name,
            floor_label=floor_label,
            original_filename=file.filename or "floorplan",
            media_type=file.content_type or "application/octet-stream",
            content=content,
        )
        return serialize(entity)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{floorplan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_floorplan(floorplan_id: UUID, service: FloorplanService = Depends(get_service)):
    try:
        service.delete(floorplan_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
