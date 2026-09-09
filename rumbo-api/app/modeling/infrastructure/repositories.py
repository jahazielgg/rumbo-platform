from uuid import UUID

from sqlalchemy.orm import Session

from ..domain.entities import MapNode, Point2D, PointOfInterest, SpatialModel, WallSegment
from ..domain.repositories import SpatialModelRepository
from .models import SpatialModelRecord


class SqlAlchemySpatialModelRepository(SpatialModelRepository):
    def __init__(self, db: Session):
        self.db = db

    def get(self, floorplan_id: UUID) -> SpatialModel | None:
        record = self.db.get(SpatialModelRecord, str(floorplan_id))
        if not record:
            return None
        return SpatialModel(
            floorplan_id=floorplan_id,
            pixels_per_meter=record.pixels_per_meter,
            walls=[
                WallSegment(
                    id=UUID(item["id"]),
                    start=Point2D(**item["start"]),
                    end=Point2D(**item["end"]),
                )
                for item in (record.walls or [])
            ],
            nodes=[
                MapNode(
                    id=UUID(item["id"]),
                    position=Point2D(**item["position"]),
                    label=item["label"],
                    kind=item.get("kind", "waypoint"),
                )
                for item in (record.nodes or [])
            ],
            pois=[
                PointOfInterest(
                    id=UUID(item["id"]),
                    name=item["name"],
                    category=item["category"],
                    position=Point2D(**item["position"]),
                    node_id=UUID(item["node_id"]),
                )
                for item in (record.pois or [])
            ],
        )

    def save(self, model: SpatialModel) -> SpatialModel:
        walls_payload = [
            {
                "id": str(wall.id),
                "start": {"x": wall.start.x, "y": wall.start.y},
                "end": {"x": wall.end.x, "y": wall.end.y},
            }
            for wall in model.walls
        ]
        nodes_payload = [
            {
                "id": str(node.id),
                "position": {"x": node.position.x, "y": node.position.y},
                "label": node.label,
                "kind": node.kind,
            }
            for node in model.nodes
        ]
        pois_payload = [
            {
                "id": str(poi.id),
                "name": poi.name,
                "category": poi.category,
                "position": {"x": poi.position.x, "y": poi.position.y},
                "node_id": str(poi.node_id),
            }
            for poi in model.pois
        ]
        record = self.db.get(SpatialModelRecord, str(model.floorplan_id))
        if record is None:
            record = SpatialModelRecord(
                floorplan_id=str(model.floorplan_id),
                pixels_per_meter=model.pixels_per_meter,
                walls=walls_payload,
                nodes=nodes_payload,
                pois=pois_payload,
            )
            self.db.add(record)
        else:
            record.pixels_per_meter = model.pixels_per_meter
            record.walls = walls_payload
            record.nodes = nodes_payload
            record.pois = pois_payload
        self.db.commit()
        return model
