from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PointInput:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class WallInput:
    id: UUID
    start: PointInput
    end: PointInput


@dataclass(frozen=True, slots=True)
class NodeInput:
    id: UUID
    position: PointInput
    label: str
    kind: str


@dataclass(frozen=True, slots=True)
class PoiInput:
    id: UUID
    name: str
    category: str
    position: PointInput
    node_id: UUID


@dataclass(frozen=True, slots=True)
class SpatialModelInput:
    pixels_per_meter: float | None
    walls: list[WallInput]
    nodes: list[NodeInput]
    pois: list[PoiInput]
