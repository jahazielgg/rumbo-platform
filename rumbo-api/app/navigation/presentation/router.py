from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.floorplans.infrastructure.models import FloorplanModel
from app.modeling.infrastructure.models import SpatialModelRecord
from app.shared_kernel.errors import ValidationError

from ..application.routing import RoutePlanningService
from ..application.services import NavigationService
from ..application.types import EdgeInput, NavigationConfigInput, RouteRequest, VerticalConnectorInput
from ..domain.entities import NavigationConfig
from ..infrastructure.repositories import SqlAlchemyNavigationConfigRepository
from ..infrastructure.routing import SqlAlchemyRouteNetworkReader
from .schemas import NavigationConfigPayload, NavigationConfigResponse, RouteRequestPayload, RouteResponse

router = APIRouter(prefix="/navigation", tags=["navigation"])


def floorplan_exists(db: Session, floorplan_id: UUID) -> bool:
    return db.get(FloorplanModel, str(floorplan_id)) is not None


def node_exists(db: Session, floorplan_id: UUID, node_id: UUID) -> bool:
    record = db.get(SpatialModelRecord, str(floorplan_id))
    return bool(record and any(item.get("id") == str(node_id) for item in (record.nodes or [])))


def get_service(db: Session = Depends(get_db)) -> NavigationService:
    return NavigationService(
        repository=SqlAlchemyNavigationConfigRepository(db),
        node_exists=lambda floorplan_id, node_id: node_exists(db, floorplan_id, node_id),
        floorplan_exists=lambda floorplan_id: floorplan_exists(db, floorplan_id),
    )


def serialize(config: NavigationConfig) -> NavigationConfigResponse:
    return NavigationConfigResponse(
        floorplan_id=config.floorplan_id,
        edges=[
            {
                "id": edge.id,
                "from_node_id": edge.from_node_id,
                "to_node_id": edge.to_node_id,
                "kind": edge.kind,
                "accessible": edge.accessible,
            }
            for edge in config.edges
        ],
        vertical_connectors=[
            {
                "id": connector.id,
                "kind": connector.kind,
                "label": connector.label,
                "source_node_id": connector.source_node_id,
                "target_floorplan_id": connector.target_floorplan_id,
                "target_node_id": connector.target_node_id,
                "accessible": connector.accessible,
                "bidirectional": connector.bidirectional,
            }
            for connector in config.vertical_connectors
        ],
    )


@router.post("/route", response_model=RouteResponse)
def calculate_route(payload: RouteRequestPayload, db: Session = Depends(get_db)):
    reader = SqlAlchemyRouteNetworkReader(db)
    service = RoutePlanningService(reader.load_for_building)
    try:
        route = service.plan(
            RouteRequest(
                start_floorplan_id=payload.start_floorplan_id,
                start_node_id=payload.start_node_id,
                destination_floorplan_id=payload.destination_floorplan_id,
                destination_node_id=payload.destination_node_id,
                accessible_only=payload.accessible_only,
            )
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RouteResponse(
        total_distance_meters=route.total_distance_meters,
        nodes=[
            {
                "floorplan_id": node.floorplan_id,
                "node_id": node.node_id,
                "label": node.label,
                "x": node.x,
                "y": node.y,
            }
            for node in route.nodes
        ],
        links=[
            {
                "from_floorplan_id": link.from_key[0],
                "from_node_id": link.from_key[1],
                "to_floorplan_id": link.to_key[0],
                "to_node_id": link.to_key[1],
                "distance_meters": link.distance_meters,
                "kind": link.kind,
                "label": link.label,
                "accessible": link.accessible,
            }
            for link in route.links
        ],
    )


@router.get("/{floorplan_id}", response_model=NavigationConfigResponse)
def get_navigation(
    floorplan_id: UUID,
    db: Session = Depends(get_db),
    service: NavigationService = Depends(get_service),
):
    if not floorplan_exists(db, floorplan_id):
        raise HTTPException(status_code=404, detail="Plano no encontrado.")
    return serialize(service.get(floorplan_id))


@router.put("/{floorplan_id}", response_model=NavigationConfigResponse)
def save_navigation(
    floorplan_id: UUID,
    payload: NavigationConfigPayload,
    db: Session = Depends(get_db),
    service: NavigationService = Depends(get_service),
):
    if not floorplan_exists(db, floorplan_id):
        raise HTTPException(status_code=404, detail="Plano no encontrado.")
    data = NavigationConfigInput(
        edges=[
            EdgeInput(
                id=edge.id,
                from_node_id=edge.from_node_id,
                to_node_id=edge.to_node_id,
                kind=edge.kind,
                accessible=edge.accessible,
            )
            for edge in payload.edges
        ],
        vertical_connectors=[
            VerticalConnectorInput(
                id=item.id,
                kind=item.kind,
                label=item.label,
                source_node_id=item.source_node_id,
                target_floorplan_id=item.target_floorplan_id,
                target_node_id=item.target_node_id,
                accessible=item.accessible,
                bidirectional=item.bidirectional,
            )
            for item in payload.vertical_connectors
        ],
    )
    try:
        return serialize(service.save(floorplan_id, data))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
