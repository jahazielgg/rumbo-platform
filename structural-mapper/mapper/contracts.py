"""Typed contracts shared by every pipeline stage.

All coordinates are pixels of the *output raster* (the image the editor displays), with
the origin at the top-left corner. Metric parameters are converted to pixels through
`Scale`. Stages never mutate objects they receive.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from shapely.geometry import LineString, Point, Polygon


@dataclass(frozen=True, slots=True)
class Scale:
    pixels_per_meter: float
    source: Literal["calibrated", "vector", "estimated", "default"]

    def px(self, meters: float) -> float:
        return meters * self.pixels_per_meter

    def meters(self, pixels: float) -> float:
        return pixels / self.pixels_per_meter


@dataclass(slots=True)
class TextLabel:
    text: str
    position: tuple[float, float]


@dataclass(slots=True)
class RasterInput:
    """Decoded floorplan ready for perception."""

    image: np.ndarray  # HxWx3 uint8 RGB
    labels: list[TextLabel] = field(default_factory=list)
    vector_walls: np.ndarray | None = None  # HxW bool, exact walls from PDF/SVG strokes
    vector_scale: float | None = None  # pixels per meter when the document declares units
    source_kind: Literal["raster", "pdf-vector", "svg-vector", "pdf-raster"] = "raster"

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def width(self) -> int:
        return int(self.image.shape[1])


@dataclass(slots=True)
class StructuralMasks:
    """Per-pixel structural perception at output resolution."""

    wall: np.ndarray  # bool
    door: np.ndarray  # bool
    window: np.ndarray  # bool
    wall_probability: np.ndarray | None = None  # float32 in [0, 1]
    thin: np.ndarray | None = None  # thin dark strokes (door swings, symbols, text)
    backend: str = "unknown"


@dataclass(slots=True)
class WallElement:
    polygon: Polygon
    kind: Literal["wall", "obstacle", "window"] = "wall"
    confidence: float = 1.0


@dataclass(slots=True)
class Opening:
    """A legal transition between two spaces (or a space and the exterior)."""

    id: str
    polygon: Polygon
    center: tuple[float, float]
    axis: LineString  # segment across the opening, along the wall
    normal: tuple[float, float]  # unit vector perpendicular to the wall
    width_px: float
    kind: Literal["door", "entrance", "passage"] = "door"
    confidence: float = 1.0
    space_ids: tuple[str | None, str | None] = (None, None)
    sources: tuple[str, ...] = ()


@dataclass(slots=True)
class Space:
    id: str
    polygon: Polygon
    kind: Literal["room", "circulation", "vertical", "void"] = "room"
    label: str | None = None
    opening_ids: list[str] = field(default_factory=list)
    area_px: float = 0.0
    narrowness: float = 0.0
    elongation: float = 1.0
    connector_kind: Literal["elevator", "stairs", "ramp"] | None = None
    confidence: float = 1.0

    @property
    def anchor(self) -> Point:
        from shapely.ops import polylabel

        try:
            return polylabel(self.polygon, tolerance=1.0)
        except Exception:  # pragma: no cover - degenerate polygons
            return self.polygon.representative_point()


@dataclass(slots=True)
class GraphNode:
    id: str
    x: float
    y: float
    kind: Literal["decision", "waypoint", "door", "entrance", "room", "connector"]
    space_id: str | None = None
    opening_id: str | None = None
    label: str | None = None
    connector_kind: str | None = None


@dataclass(slots=True)
class GraphEdge:
    from_id: str
    to_id: str
    kind: Literal["corridor", "doorway"] = "corridor"
    length_px: float = 0.0


@dataclass(slots=True)
class NavigationGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


@dataclass(slots=True)
class ValidationIssue:
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    subject_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ValidationReport:
    status: Literal["ok", "warnings", "errors"] = "ok"
    issues: list[ValidationIssue] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "error":
            self.status = "errors"
        elif issue.severity == "warning" and self.status == "ok":
            self.status = "warnings"


@dataclass(slots=True)
class Scene:
    """Full structural understanding of one floor."""

    width: int
    height: int
    scale: Scale
    walls: list[WallElement] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)
    spaces: list[Space] = field(default_factory=list)
    walkable: list[Polygon] = field(default_factory=list)
    graph: NavigationGraph = field(default_factory=NavigationGraph)
    validation: ValidationReport = field(default_factory=ValidationReport)
    diagnostics: dict[str, float | int | str] = field(default_factory=dict)
    labels: list[TextLabel] = field(default_factory=list)
