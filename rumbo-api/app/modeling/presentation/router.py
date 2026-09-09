from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.floorplans.infrastructure.models import FloorplanModel
from app.infrastructure.database import get_db
from app.infrastructure.settings import get_settings
from app.navigation.presentation.schemas import NavigationConfigResponse
from app.shared_kernel.errors import ValidationError

from ..application.auto_model import AutoModelingService
from ..application.services import ModelingService
from ..application.types import NodeInput, PointInput, PoiInput, SpatialModelInput, WallInput
from ..domain.entities import SpatialModel
from ..domain.structural import StructuralPolygon
from ..infrastructure.repositories import SqlAlchemySpatialModelRepository
from ..infrastructure.structural_parser import StructuralMapperClient
from ..infrastructure.structural_repository import SqlAlchemyStructuralMapRepository
from .auto_schemas import AutoModelResponse, StructuralMapResponse, ValidationReportSchema
from .schemas import SpatialModelPayload, SpatialModelResponse

router = APIRouter(prefix="/modeling", tags=["modeling"])


def get_service(db: Session = Depends(get_db)) -> ModelingService:
    return ModelingService(SqlAlchemySpatialModelRepository(db))


def ensure_floorplan(db: Session, floorplan_id: UUID) -> FloorplanModel:
    record = db.get(FloorplanModel, str(floorplan_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Plano no encontrado.")
    return record


def serialize(model: SpatialModel) -> SpatialModelResponse:
    return SpatialModelResponse(
        floorplan_id=model.floorplan_id,
        pixels_per_meter=model.pixels_per_meter,
        walls=[
            {
                "id": wall.id,
                "start": {"x": wall.start.x, "y": wall.start.y},
                "end": {"x": wall.end.x, "y": wall.end.y},
            }
            for wall in model.walls
        ],
        nodes=[
            {
                "id": node.id,
                "position": {"x": node.position.x, "y": node.position.y},
                "label": node.label,
                "kind": node.kind,
            }
            for node in model.nodes
        ],
        pois=[
            {
                "id": poi.id,
                "name": poi.name,
                "category": poi.category,
                "position": {"x": poi.position.x, "y": poi.position.y},
                "node_id": poi.node_id,
            }
            for poi in model.pois
        ],
    )


def _polygon_payload(polygon: StructuralPolygon) -> dict:
    return {
        "outer": [{"x": point.x, "y": point.y} for point in polygon.outer],
        "holes": [
            [{"x": point.x, "y": point.y} for point in ring]
            for ring in polygon.holes
        ],
    }


PDF_RASTER_SCALE = 2.0  # must match the preview zoom so proposals align with the editor


def _analysis_bytes(record: FloorplanModel) -> tuple[bytes, str]:
    """Return the original document. PDFs keep their vector geometry: the mapper
    rasterizes them itself at the preview zoom and also reads strokes and text."""
    settings = get_settings()
    path = (settings.upload_path / record.stored_filename).resolve()
    if settings.upload_path not in path.parents:
        raise HTTPException(status_code=400, detail="Ruta de plano inválida.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="El archivo físico del plano no existe.")
    return path.read_bytes(), record.media_type


@router.post("/{floorplan_id}/auto-model", response_model=AutoModelResponse)
def auto_model(
    floorplan_id: UUID,
    db: Session = Depends(get_db),
    service: ModelingService = Depends(get_service),
):
    record = ensure_floorplan(db, floorplan_id)
    content, media_type = _analysis_bytes(record)
    settings = get_settings()
    parser = StructuralMapperClient(
        settings.structural_mapper_url,
        timeout_seconds=settings.structural_mapper_timeout_seconds,
    )
    auto_service = AutoModelingService(parser, SqlAlchemyStructuralMapRepository(db))
    try:
        proposal = auto_service.propose(
            floorplan_id=floorplan_id,
            content=content,
            media_type=media_type,
            current_model=service.get(floorplan_id),
            raster_scale=PDF_RASTER_SCALE,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    structural = proposal.analysis.structural_map
    navigation = proposal.navigation
    return AutoModelResponse(
        model=serialize(proposal.model),
        navigation=NavigationConfigResponse(
            floorplan_id=navigation.floorplan_id,
            edges=[
                {
                    "id": edge.id,
                    "from_node_id": edge.from_node_id,
                    "to_node_id": edge.to_node_id,
                    "kind": edge.kind,
                    "accessible": edge.accessible,
                }
                for edge in navigation.edges
            ],
            vertical_connectors=[],
        ),
        structural=StructuralMapResponse(
            parser=structural.parser,
            parser_version=structural.parser_version,
            image_width=structural.image_width,
            image_height=structural.image_height,
            wall_polygons=len(structural.wall_polygons),
            obstacles=[_polygon_payload(item) for item in structural.obstacle_polygons],
            doors=[
                {
                    "id": opening.id,
                    "kind": opening.kind,
                    "polygon": _polygon_payload(opening.polygon),
                    "confidence": opening.confidence,
                    "width_px": opening.width_px,
                    "center": {"x": opening.center.x, "y": opening.center.y} if opening.center else None,
                    "spaces": list(opening.space_keys),
                }
                for opening in structural.doors
            ],
            windows=len(structural.window_polygons),
            spaces=[
                {
                    "id": space.id,
                    "kind": space.kind,
                    "label": space.label,
                    "connector_kind": space.connector_kind,
                    "confidence": space.confidence,
                    "polygon": _polygon_payload(space.polygon),
                }
                for space in structural.spaces
            ],
            walkable_areas=len(structural.walkable_areas),
            validation=ValidationReportSchema(
                status=structural.validation.status,
                issues=[
                    {"code": i.code, "severity": i.severity, "message": i.message, "subjects": list(i.subjects)}
                    for i in structural.validation.issues
                ],
                metrics=structural.validation.metrics,
            ),
            estimated_pixels_per_meter=structural.estimated_pixels_per_meter,
            scale_source=structural.scale_source,
        ),
        diagnostics=proposal.diagnostics,
    )


@router.get("/{floorplan_id}", response_model=SpatialModelResponse)
def get_model(
    floorplan_id: UUID,
    db: Session = Depends(get_db),
    service: ModelingService = Depends(get_service),
):
    ensure_floorplan(db, floorplan_id)
    return serialize(service.get(floorplan_id))


@router.put("/{floorplan_id}", response_model=SpatialModelResponse)
def save_model(
    floorplan_id: UUID,
    payload: SpatialModelPayload,
    db: Session = Depends(get_db),
    service: ModelingService = Depends(get_service),
):
    ensure_floorplan(db, floorplan_id)
    data = SpatialModelInput(
        pixels_per_meter=payload.pixels_per_meter,
        walls=[
            WallInput(
                id=wall.id,
                start=PointInput(x=wall.start.x, y=wall.start.y),
                end=PointInput(x=wall.end.x, y=wall.end.y),
            )
            for wall in payload.walls
        ],
        nodes=[
            NodeInput(
                id=node.id,
                position=PointInput(x=node.position.x, y=node.position.y),
                label=node.label,
                kind=node.kind,
            )
            for node in payload.nodes
        ],
        pois=[
            PoiInput(
                id=poi.id,
                name=poi.name,
                category=poi.category,
                position=PointInput(x=poi.position.x, y=poi.position.y),
                node_id=poi.node_id,
            )
            for poi in payload.pois
        ],
    )
    try:
        return serialize(service.save(floorplan_id, data))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
