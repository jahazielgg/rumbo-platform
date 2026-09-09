from uuid import UUID

from pydantic import BaseModel, Field

from app.navigation.presentation.schemas import NavigationConfigResponse
from .schemas import PointSchema, SpatialModelResponse


class StructuralPolygonSchema(BaseModel):
    outer: list[PointSchema]
    holes: list[list[PointSchema]] = Field(default_factory=list)


class OpeningSchema(BaseModel):
    id: UUID
    kind: str
    polygon: StructuralPolygonSchema
    confidence: float
    width_px: float = 0.0
    center: PointSchema | None = None
    spaces: list[str | None] = Field(default_factory=list)


class SpaceSchema(BaseModel):
    id: UUID
    kind: str
    label: str | None = None
    connector_kind: str | None = None
    confidence: float = 1.0
    polygon: StructuralPolygonSchema


class ValidationIssueSchema(BaseModel):
    code: str
    severity: str
    message: str
    subjects: list[str] = Field(default_factory=list)


class ValidationReportSchema(BaseModel):
    status: str
    issues: list[ValidationIssueSchema] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class StructuralMapResponse(BaseModel):
    parser: str
    parser_version: str
    image_width: int
    image_height: int
    wall_polygons: int
    obstacles: list[StructuralPolygonSchema] = Field(default_factory=list)
    doors: list[OpeningSchema]
    windows: int
    spaces: list[SpaceSchema]
    walkable_areas: int
    validation: ValidationReportSchema
    estimated_pixels_per_meter: float | None = None
    scale_source: str | None = None


class AutoModelResponse(BaseModel):
    model: SpatialModelResponse
    navigation: NavigationConfigResponse
    structural: StructuralMapResponse
    diagnostics: dict[str, int | float | str] = Field(default_factory=dict)
