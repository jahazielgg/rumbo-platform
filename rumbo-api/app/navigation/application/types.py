from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EdgeInput:
    id: UUID
    from_node_id: UUID
    to_node_id: UUID
    kind: str
    accessible: bool


@dataclass(frozen=True, slots=True)
class VerticalConnectorInput:
    id: UUID
    kind: str
    label: str
    source_node_id: UUID
    target_floorplan_id: UUID
    target_node_id: UUID
    accessible: bool
    bidirectional: bool


@dataclass(frozen=True, slots=True)
class NavigationConfigInput:
    edges: list[EdgeInput]
    vertical_connectors: list[VerticalConnectorInput]


@dataclass(frozen=True, slots=True)
class RouteNodeSource:
    id: UUID
    label: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class RouteEdgeSource:
    from_node_id: UUID
    to_node_id: UUID
    accessible: bool


@dataclass(frozen=True, slots=True)
class RouteWallSource:
    start_x: float
    start_y: float
    end_x: float
    end_y: float


@dataclass(frozen=True, slots=True)
class RouteConnectorSource:
    kind: str
    label: str
    source_node_id: UUID
    target_floorplan_id: UUID
    target_node_id: UUID
    accessible: bool
    bidirectional: bool


@dataclass(frozen=True, slots=True)
class RouteFloorSource:
    floorplan_id: UUID
    building_name: str
    floor_label: str
    pixels_per_meter: float | None
    nodes: list[RouteNodeSource]
    edges: list[RouteEdgeSource]
    walls: list[RouteWallSource]
    connectors: list[RouteConnectorSource]


@dataclass(frozen=True, slots=True)
class RouteRequest:
    start_floorplan_id: UUID
    start_node_id: UUID
    destination_floorplan_id: UUID
    destination_node_id: UUID
    accessible_only: bool = False
