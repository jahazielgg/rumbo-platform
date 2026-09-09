from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PointSchema(BaseModel):
    x: float
    y: float


class WallSchema(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    start: PointSchema
    end: PointSchema


class NodeSchema(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    position: PointSchema
    label: str = Field(min_length=1, max_length=80)
    kind: str = Field(default="waypoint", min_length=1, max_length=40)


class PoiSchema(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    position: PointSchema
    node_id: UUID


class SpatialModelPayload(BaseModel):
    pixels_per_meter: float | None = Field(default=None, gt=0)
    walls: list[WallSchema] = Field(default_factory=list)
    nodes: list[NodeSchema] = Field(default_factory=list)
    pois: list[PoiSchema] = Field(default_factory=list)


class SpatialModelResponse(SpatialModelPayload):
    floorplan_id: UUID
