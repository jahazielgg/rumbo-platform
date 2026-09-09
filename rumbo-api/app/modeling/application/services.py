from uuid import UUID

from .types import SpatialModelInput
from ..domain.entities import MapNode, Point2D, PointOfInterest, SpatialModel, WallSegment
from ..domain.repositories import SpatialModelRepository


class ModelingService:
    def __init__(self, repository: SpatialModelRepository):
        self.repository = repository

    def get(self, floorplan_id: UUID) -> SpatialModel:
        return self.repository.get(floorplan_id) or SpatialModel(floorplan_id=floorplan_id)

    def save(self, floorplan_id: UUID, data: SpatialModelInput) -> SpatialModel:
        walls = [
            WallSegment(
                id=item.id,
                start=Point2D(x=item.start.x, y=item.start.y),
                end=Point2D(x=item.end.x, y=item.end.y),
            )
            for item in data.walls
        ]
        nodes = [
            MapNode(
                id=item.id,
                position=Point2D(x=item.position.x, y=item.position.y),
                label=item.label,
                kind=item.kind,
            )
            for item in data.nodes
        ]
        pois = [
            PointOfInterest(
                id=item.id,
                name=item.name,
                category=item.category,
                position=Point2D(x=item.position.x, y=item.position.y),
                node_id=item.node_id,
            )
            for item in data.pois
        ]
        model = SpatialModel(
            floorplan_id=floorplan_id,
            pixels_per_meter=data.pixels_per_meter,
            walls=walls,
            nodes=nodes,
            pois=pois,
        )
        return self.repository.save(model)
