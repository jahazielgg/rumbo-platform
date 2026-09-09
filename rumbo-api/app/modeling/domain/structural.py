from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class StructuralPoint:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class StructuralPolygon:
    outer: tuple[StructuralPoint, ...]
    holes: tuple[tuple[StructuralPoint, ...], ...] = ()


OPENING_KINDS = {"door", "entrance", "passage"}
SPACE_KINDS = {"room", "circulation", "vertical", "void", "unknown"}


@dataclass(frozen=True, slots=True)
class Opening:
    """A legal transition between two spaces or between a space and the outside."""

    id: UUID
    polygon: StructuralPolygon
    kind: str = "door"
    confidence: float = 1.0
    width_px: float = 0.0
    center: StructuralPoint | None = None
    space_keys: tuple[str | None, str | None] = (None, None)
    source_key: str | None = None

    @classmethod
    def create(cls, polygon: StructuralPolygon, kind: str = "door", confidence: float = 1.0, **extra) -> "Opening":
        return cls(id=uuid4(), polygon=polygon, kind=kind if kind in OPENING_KINDS else "door", confidence=confidence, **extra)


# Backwards compatible alias: v2 called every opening a door.
DoorOpening = Opening


@dataclass(frozen=True, slots=True)
class SpaceArea:
    id: UUID
    polygon: StructuralPolygon
    kind: str = "unknown"
    label: str | None = None
    connector_kind: str | None = None
    confidence: float = 1.0
    source_key: str | None = None

    @classmethod
    def create(cls, polygon: StructuralPolygon, kind: str = "unknown", **extra) -> "SpaceArea":
        return cls(id=uuid4(), polygon=polygon, kind=kind if kind in SPACE_KINDS else "unknown", **extra)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: str
    message: str
    subjects: tuple[str, ...] = ()


@dataclass(slots=True)
class ValidationReport:
    status: str = "ok"
    issues: list[ValidationIssue] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return self.status == "errors"


@dataclass(slots=True)
class StructuralMap:
    floorplan_id: UUID
    parser: str
    parser_version: str
    image_width: int
    image_height: int
    wall_polygons: list[StructuralPolygon] = field(default_factory=list)
    obstacle_polygons: list[StructuralPolygon] = field(default_factory=list)
    doors: list[Opening] = field(default_factory=list)  # every opening, including entrances
    window_polygons: list[StructuralPolygon] = field(default_factory=list)
    spaces: list[SpaceArea] = field(default_factory=list)
    walkable_areas: list[SpaceArea] = field(default_factory=list)
    validation: ValidationReport = field(default_factory=ValidationReport)
    estimated_pixels_per_meter: float | None = None
    scale_source: str | None = None

    @property
    def openings(self) -> list[Opening]:
        return self.doors

    @property
    def entrances(self) -> list[Opening]:
        return [item for item in self.doors if item.kind == "entrance"]


NODE_KINDS = {"waypoint", "decision", "entrance", "door", "room", "connector"}


@dataclass(frozen=True, slots=True)
class ProposedNode:
    key: str
    position: StructuralPoint
    kind: str = "waypoint"
    label: str | None = None
    space_key: str | None = None
    connector_kind: str | None = None


@dataclass(frozen=True, slots=True)
class ProposedEdge:
    from_key: str
    to_key: str
    kind: str = "corridor"


@dataclass(slots=True)
class StructuralAnalysis:
    structural_map: StructuralMap
    nodes: list[ProposedNode]
    edges: list[ProposedEdge]
    diagnostics: dict[str, int | float | str] = field(default_factory=dict)
