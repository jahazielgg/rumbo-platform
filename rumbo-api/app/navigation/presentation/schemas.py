from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EdgeSchema(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    from_node_id: UUID
    to_node_id: UUID
    kind: str = "corridor"
    accessible: bool = True


class VerticalConnectorSchema(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: str
    label: str = Field(min_length=1, max_length=120)
    source_node_id: UUID
    target_floorplan_id: UUID
    target_node_id: UUID
    accessible: bool = True
    bidirectional: bool = True


class NavigationConfigPayload(BaseModel):
    edges: list[EdgeSchema] = Field(default_factory=list)
    vertical_connectors: list[VerticalConnectorSchema] = Field(default_factory=list)


class NavigationConfigResponse(NavigationConfigPayload):
    floorplan_id: UUID


class RouteRequestPayload(BaseModel):
    start_floorplan_id: UUID
    start_node_id: UUID
    destination_floorplan_id: UUID
    destination_node_id: UUID
    accessible_only: bool = False


class RouteNodeResponse(BaseModel):
    floorplan_id: UUID
    node_id: UUID
    label: str
    x: float
    y: float


class RouteLinkResponse(BaseModel):
    from_floorplan_id: UUID
    from_node_id: UUID
    to_floorplan_id: UUID
    to_node_id: UUID
    distance_meters: float
    kind: str
    label: str | None = None
    accessible: bool


class RouteResponse(BaseModel):
    total_distance_meters: float
    nodes: list[RouteNodeResponse]
    links: list[RouteLinkResponse]
