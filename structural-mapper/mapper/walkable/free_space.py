"""Walkable area: interior spaces shrunk by a body clearance, joined through openings."""
from __future__ import annotations

from shapely.geometry import Polygon
from shapely.ops import polylabel, unary_union

from ..contracts import Opening, Scale, Space
from ..geometry import as_polygons

CLEARANCE_M = 0.25


def walkable_by_space(spaces: list[Space], scale: Scale) -> dict[str, Polygon]:
    result: dict[str, Polygon] = {}
    clearance = scale.px(CLEARANCE_M)
    for space in spaces:
        if space.kind == "void":
            continue
        try:
            radius = space.polygon.exterior.distance(polylabel(space.polygon, tolerance=1.0))
        except Exception:
            radius = clearance
        shrink = min(clearance, max(1.0, radius * 0.4))
        shrunk = space.polygon.buffer(-shrink)
        parts = [p for p in as_polygons(shrunk) if p.area > 0]
        if not parts:
            result[space.id] = space.polygon
            continue
        result[space.id] = max(parts, key=lambda p: p.area) if len(parts) > 1 and max(p.area for p in parts) > 0.9 * shrunk.area else unary_union(parts)  # type: ignore[assignment]
    return result


def walkable_union(walkable: dict[str, Polygon], openings: list[Opening], scale: Scale) -> list[Polygon]:
    grow = max(1.0, scale.px(0.1))
    geometries = list(walkable.values()) + [o.polygon.buffer(grow) for o in openings if o.kind != "entrance"]
    return as_polygons(unary_union(geometries))
