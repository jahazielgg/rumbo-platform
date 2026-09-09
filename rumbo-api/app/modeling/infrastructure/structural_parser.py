from __future__ import annotations

from uuid import UUID

import httpx

from app.shared_kernel.errors import ValidationError

from ..application.ports import StructuralParser
from ..domain.structural import (
    Opening,
    ProposedEdge,
    ProposedNode,
    SpaceArea,
    StructuralAnalysis,
    StructuralMap,
    StructuralPoint,
    StructuralPolygon,
    ValidationIssue,
    ValidationReport,
)


def _polygon(payload: dict) -> StructuralPolygon:
    return StructuralPolygon(
        outer=tuple(StructuralPoint(x=float(x), y=float(y)) for x, y in payload.get("outer", payload.get("polygon", []))),
        holes=tuple(
            tuple(StructuralPoint(x=float(x), y=float(y)) for x, y in ring)
            for ring in payload.get("holes", [])
        ),
    )


def _space(item: dict) -> SpaceArea | None:
    polygon = item.get("polygon", [])
    if isinstance(polygon, dict):
        shape = _polygon(polygon)
    else:
        shape = StructuralPolygon(outer=tuple(StructuralPoint(x=float(x), y=float(y)) for x, y in polygon))
    if len(shape.outer) < 3:
        return None
    return SpaceArea.create(
        shape,
        kind=item.get("kind", "unknown"),
        label=item.get("label"),
        connector_kind=item.get("connector_kind"),
        confidence=float(item.get("confidence", 1.0)),
        source_key=item.get("id"),
    )


class StructuralMapperClient(StructuralParser):
    """HTTP adapter for the `structural-mapper` service (v3 payload)."""

    def __init__(self, base_url: str, timeout_seconds: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def analyze(
        self,
        *,
        floorplan_id: UUID,
        content: bytes,
        media_type: str,
        pixels_per_meter: float | None = None,
        raster_scale: float = 2.0,
    ) -> StructuralAnalysis:
        data_fields: dict[str, str] = {"raster_scale": str(raster_scale)}
        if pixels_per_meter:
            data_fields["pixels_per_meter"] = str(pixels_per_meter)
        try:
            response = httpx.post(
                f"{self.base_url}/analyze",
                files={"file": ("floorplan", content, media_type)},
                data=data_fields,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise ValidationError(f"El parser estructural rechazó el plano: {detail}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ValidationError(
                "El motor de Structural Mapping no está disponible. Verifica el servicio structural-mapper."
            ) from exc
        return parse_analysis(floorplan_id, data)


def parse_analysis(floorplan_id: UUID, data: dict) -> StructuralAnalysis:
    size = data["image_size"]
    walls = [_polygon(item) for item in data.get("walls", [])]
    obstacles = [_polygon(item) for item in data.get("obstacles", [])]
    windows = [_polygon(item) for item in data.get("windows", [])]

    openings: list[Opening] = []
    if data.get("openings"):
        for item in data["openings"]:
            spaces = item.get("spaces") or [None, None]
            center = item.get("center")
            openings.append(
                Opening.create(
                    _polygon(item["polygon"]),
                    kind=item.get("kind", "door"),
                    confidence=float(item.get("confidence", 1.0)),
                    width_px=float(item.get("width_px", 0.0)),
                    center=StructuralPoint(float(center[0]), float(center[1])) if center else None,
                    space_keys=(spaces[0], spaces[1] if len(spaces) > 1 else None),
                    source_key=item.get("id"),
                )
            )
    else:  # v2 payloads only carried door polygons
        openings = [Opening.create(_polygon(item)) for item in data.get("doors", [])]

    spaces = [space for space in (_space(item) for item in data.get("spaces", [])) if space is not None]
    walkable = [
        SpaceArea.create(_polygon(item["polygon"]) if isinstance(item.get("polygon"), dict) else StructuralPolygon(outer=tuple(StructuralPoint(float(x), float(y)) for x, y in item.get("polygon", []))), kind=item.get("kind", "walkable"))
        for item in data.get("walkable", [])
    ]
    walkable = [item for item in walkable if len(item.polygon.outer) >= 3]

    validation_payload = data.get("validation", {})
    validation = ValidationReport(
        status=validation_payload.get("status", "ok"),
        issues=[
            ValidationIssue(
                code=str(issue.get("code", "unknown")),
                severity=str(issue.get("severity", "info")),
                message=str(issue.get("message", "")),
                subjects=tuple(str(s) for s in issue.get("subjects", [])),
            )
            for issue in validation_payload.get("issues", [])
        ],
        metrics={str(k): float(v) for k, v in validation_payload.get("metrics", {}).items()},
    )
    scale = data.get("scale") or {}

    structural_map = StructuralMap(
        floorplan_id=floorplan_id,
        parser=data.get("parser", "structural-mapper"),
        parser_version=str(data.get("parser_version", "1")),
        image_width=int(size["width"]),
        image_height=int(size["height"]),
        wall_polygons=walls,
        obstacle_polygons=obstacles,
        doors=openings,
        window_polygons=windows,
        spaces=spaces,
        walkable_areas=walkable,
        validation=validation,
        estimated_pixels_per_meter=float(scale["pixels_per_meter"]) if scale.get("pixels_per_meter") else None,
        scale_source=scale.get("source"),
    )
    nodes = [
        ProposedNode(
            key=str(item["id"]),
            position=StructuralPoint(x=float(item["x"]), y=float(item["y"])),
            kind=item.get("kind", "waypoint"),
            label=item.get("label"),
            space_key=item.get("space_id"),
            connector_kind=item.get("connector_kind"),
        )
        for item in data.get("graph", {}).get("nodes", [])
    ]
    edges = [
        ProposedEdge(from_key=str(item["from"]), to_key=str(item["to"]), kind=item.get("kind", "corridor"))
        for item in data.get("graph", {}).get("edges", [])
    ]
    diagnostics = {}
    for key, value in data.get("diagnostics", {}).items():
        diagnostics[str(key)] = value if isinstance(value, (int, float, str)) else str(value)
    return StructuralAnalysis(structural_map=structural_map, nodes=nodes, edges=edges, diagnostics=diagnostics)


# Backwards compatible name used by earlier composition code.
BuildingCvStructuralParser = StructuralMapperClient
