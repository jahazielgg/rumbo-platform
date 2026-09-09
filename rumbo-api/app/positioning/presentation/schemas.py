from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class QRAnchorSchema(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    code: str = Field(min_length=1, max_length=220)
    label: str = Field(min_length=1, max_length=120)
    node_id: UUID


class PositioningConfigPayload(BaseModel):
    qr_anchors: list[QRAnchorSchema] = Field(default_factory=list)


class PositioningConfigResponse(PositioningConfigPayload):
    floorplan_id: UUID
