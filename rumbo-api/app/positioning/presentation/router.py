from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.floorplans.infrastructure.models import FloorplanModel
from app.modeling.infrastructure.models import SpatialModelRecord
from app.shared_kernel.errors import ValidationError

from ..application.services import PositioningService
from ..application.types import PositioningConfigInput, QRAnchorInput
from ..domain.entities import PositioningConfig
from ..infrastructure.repositories import SqlAlchemyPositioningConfigRepository
from .schemas import PositioningConfigPayload, PositioningConfigResponse

router = APIRouter(prefix="/positioning", tags=["positioning"])


def floorplan_exists(db: Session, floorplan_id: UUID) -> bool:
    return db.get(FloorplanModel, str(floorplan_id)) is not None


def node_exists(db: Session, floorplan_id: UUID, node_id: UUID) -> bool:
    record = db.get(SpatialModelRecord, str(floorplan_id))
    return bool(record and any(item.get("id") == str(node_id) for item in (record.nodes or [])))


def get_service(db: Session = Depends(get_db)) -> PositioningService:
    return PositioningService(
        repository=SqlAlchemyPositioningConfigRepository(db),
        node_exists=lambda floorplan_id, node_id: node_exists(db, floorplan_id, node_id),
    )


def serialize(config: PositioningConfig) -> PositioningConfigResponse:
    return PositioningConfigResponse(
        floorplan_id=config.floorplan_id,
        qr_anchors=[
            {"id": anchor.id, "code": anchor.code, "label": anchor.label, "node_id": anchor.node_id}
            for anchor in config.qr_anchors
        ],
    )


@router.get("/{floorplan_id}", response_model=PositioningConfigResponse)
def get_positioning(
    floorplan_id: UUID,
    db: Session = Depends(get_db),
    service: PositioningService = Depends(get_service),
):
    if not floorplan_exists(db, floorplan_id):
        raise HTTPException(status_code=404, detail="Plano no encontrado.")
    return serialize(service.get(floorplan_id))


@router.put("/{floorplan_id}", response_model=PositioningConfigResponse)
def save_positioning(
    floorplan_id: UUID,
    payload: PositioningConfigPayload,
    db: Session = Depends(get_db),
    service: PositioningService = Depends(get_service),
):
    if not floorplan_exists(db, floorplan_id):
        raise HTTPException(status_code=404, detail="Plano no encontrado.")
    data = PositioningConfigInput(
        qr_anchors=[
            QRAnchorInput(id=item.id, code=item.code, label=item.label, node_id=item.node_id)
            for item in payload.qr_anchors
        ]
    )
    try:
        return serialize(service.save(floorplan_id, data))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
