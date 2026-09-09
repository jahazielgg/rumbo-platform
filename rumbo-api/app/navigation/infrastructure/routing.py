from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.floorplans.infrastructure.models import FloorplanModel
from app.modeling.infrastructure.models import SpatialModelRecord

from ..application.types import (
    RouteConnectorSource,
    RouteEdgeSource,
    RouteFloorSource,
    RouteNodeSource,
    RouteWallSource,
)
from .models import NavigationConfigRecord


class SqlAlchemyRouteNetworkReader:
    def __init__(self, db: Session):
        self.db = db

    def load_for_building(self, start_floorplan_id: UUID) -> list[RouteFloorSource]:
        start = self.db.get(FloorplanModel, str(start_floorplan_id))
        if start is None:
            return []
        floorplans = self.db.scalars(
            select(FloorplanModel).where(FloorplanModel.building_name == start.building_name)
        ).all()
        result: list[RouteFloorSource] = []
        for floor in floorplans:
            spatial = self.db.get(SpatialModelRecord, floor.id)
            navigation = self.db.get(NavigationConfigRecord, floor.id)
            if spatial is None:
                continue
            result.append(
                RouteFloorSource(
                    floorplan_id=UUID(floor.id),
                    building_name=floor.building_name,
                    floor_label=floor.floor_label,
                    pixels_per_meter=spatial.pixels_per_meter,
                    nodes=[
                        RouteNodeSource(
                            id=UUID(item["id"]),
                            label=item.get("label", "Nodo"),
                            x=float(item["position"]["x"]),
                            y=float(item["position"]["y"]),
                        )
                        for item in (spatial.nodes or [])
                    ],
                    edges=[
                        RouteEdgeSource(
                            from_node_id=UUID(item["from_node_id"]),
                            to_node_id=UUID(item["to_node_id"]),
                            accessible=bool(item.get("accessible", True)),
                        )
                        for item in ((navigation.edges if navigation else []) or [])
                    ],
                    walls=[
                        RouteWallSource(
                            start_x=float(item["start"]["x"]),
                            start_y=float(item["start"]["y"]),
                            end_x=float(item["end"]["x"]),
                            end_y=float(item["end"]["y"]),
                        )
                        for item in (spatial.walls or [])
                    ],
                    connectors=[
                        RouteConnectorSource(
                            kind=item["kind"],
                            label=item["label"],
                            source_node_id=UUID(item["source_node_id"]),
                            target_floorplan_id=UUID(item["target_floorplan_id"]),
                            target_node_id=UUID(item["target_node_id"]),
                            accessible=bool(item.get("accessible", True)),
                            bidirectional=bool(item.get("bidirectional", True)),
                        )
                        for item in ((navigation.vertical_connectors if navigation else []) or [])
                    ],
                )
            )
        return result
