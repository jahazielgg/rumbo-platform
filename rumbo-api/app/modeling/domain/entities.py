from dataclasses import dataclass, field
from math import hypot
from uuid import UUID, uuid4

from app.shared_kernel.errors import ValidationError


@dataclass(frozen=True, slots=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class WallSegment:
    id: UUID
    start: Point2D
    end: Point2D

    @classmethod
    def create(cls, start: Point2D, end: Point2D) -> "WallSegment":
        if pixel_distance(start, end) < 1:
            raise ValidationError("Una pared debe tener una longitud visible.")
        return cls(id=uuid4(), start=start, end=end)


@dataclass(frozen=True, slots=True)
class MapNode:
    id: UUID
    position: Point2D
    label: str
    kind: str = "waypoint"

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValidationError("El nodo debe tener una etiqueta.")


@dataclass(frozen=True, slots=True)
class PointOfInterest:
    id: UUID
    name: str
    category: str
    position: Point2D
    node_id: UUID

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("El punto de atención debe tener un nombre.")
        if not self.category.strip():
            raise ValidationError("El punto de atención debe tener una categoría.")


@dataclass(slots=True)
class SpatialModel:
    floorplan_id: UUID
    pixels_per_meter: float | None = None
    walls: list[WallSegment] = field(default_factory=list)
    nodes: list[MapNode] = field(default_factory=list)
    pois: list[PointOfInterest] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.pixels_per_meter is not None and self.pixels_per_meter <= 0:
            raise ValidationError("La escala debe ser mayor a cero.")
        self._validate_references()

    def calibrate(self, *, a: Point2D, b: Point2D, meters: float) -> None:
        if meters <= 0:
            raise ValidationError("La distancia real debe ser mayor a cero.")
        px = pixel_distance(a, b)
        if px < 1:
            raise ValidationError("Los puntos de calibración deben ser distintos.")
        self.pixels_per_meter = px / meters

    def meters_between(self, a: Point2D, b: Point2D) -> float | None:
        if not self.pixels_per_meter:
            return None
        return pixel_distance(a, b) / self.pixels_per_meter

    def has_node(self, node_id: UUID) -> bool:
        return any(node.id == node_id for node in self.nodes)

    def _validate_references(self) -> None:
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValidationError("No puede haber nodos duplicados.")
        for poi in self.pois:
            if poi.node_id not in node_ids:
                raise ValidationError(f"El punto de atención '{poi.name}' debe estar asociado a un nodo existente.")


def pixel_distance(a: Point2D, b: Point2D) -> float:
    return hypot(b.x - a.x, b.y - a.y)
