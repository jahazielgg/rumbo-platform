"""Door/opening detection.

Two independent sources are fused:

* **Geometric gaps** — a morphological closing of the blocked mask fills door-sized
  gaps between wall ends. The filled region is a candidate opening if it touches the
  wall on two separate sides and is door-sized. This works on any plan style and needs
  no training data.
* **ML door pixels** — CNN door predictions confirm a gap (higher confidence) or add
  openings the gap detector could not see (e.g. doors drawn as symbols on a continuous
  wall line).

Whether an opening really separates two spaces is decided later by `inference.spaces`.
"""
from __future__ import annotations

from itertools import count

import cv2
import numpy as np
from shapely.geometry import Polygon

from ..contracts import Opening, Scale, StructuralMasks, WallElement
from ..geometry import components, components_cropped, line_kernel, oriented_box, rasterize, segment

MIN_DOOR_M = 0.55
MAX_DOOR_M = 3.0
MAX_WALL_M = 0.9


def detect_openings(masks: StructuralMasks, walls: list[WallElement], scale: Scale, shape: tuple[int, int]) -> list[Opening]:
    blocked = rasterize([w.polygon for w in walls], shape)
    ids = count(1)
    openings: list[Opening] = []

    for kernel_m, min_width_m, max_width_m in ((1.5, MIN_DOOR_M, 1.7), (3.0, 1.5, MAX_DOOR_M)):
        for axis, component, origin in _gap_components(blocked, scale, kernel_m):
            candidate = _opening_from_component(component, blocked, scale, min_width_m, max_width_m, ids, ("gap",), 0.7, axis=axis, origin=origin)
            if candidate is None:
                continue
            overlapping = [o for o in openings if o.polygon.intersects(candidate.polygon)]
            if overlapping:
                # keep the tightest measurement (the orientation parallel to the wall)
                best = min(overlapping, key=lambda o: o.polygon.area)
                if candidate.polygon.area >= best.polygon.area:
                    continue
                for o in overlapping:
                    openings.remove(o)
                candidate.id = best.id
            if masks.thin is not None and swing_evidence(masks.thin, candidate.center, candidate.normal, candidate.width_px, scale) > 0:
                candidate.sources = ("gap", "swing")
                candidate.confidence = 0.85
            openings.append(candidate)

    for component, origin, _ in components_cropped(masks.door, min_area=scale.px(0.25) ** 2):
        candidate = _opening_from_component(component, blocked, scale, 0.45, 3.2, ids, ("ml",), 0.6, check_contacts=False, origin=origin)
        if candidate is None:
            continue
        matched = False
        for existing in openings:
            if existing.polygon.intersects(candidate.polygon):
                existing.sources = tuple(sorted(set(existing.sources) | {"ml"}))
                existing.confidence = 0.95
                matched = True
        if not matched:
            openings.append(candidate)
    return openings


def _gap_components(blocked: np.ndarray, scale: Scale, kernel_m: float, orientations: int = 12):
    """Yield (axis, component) for door-sized gap fills, one orientation at a time.

    A disc-shaped closing cannot bridge a doorway in a thin wall (the eroded disc never
    fits in the bridged band), so we close with *line* kernels: a line of length L fills
    every gap up to L in walls parallel to it. Orientations are evaluated separately so
    that diagonal fills at corners never merge with real doorway fills.
    """
    length = max(3, int(round(scale.px(kernel_m))))
    if length % 2 == 0:
        length += 1
    src = cv2.copyMakeBorder(blocked.astype(np.uint8), length, length, length, length, cv2.BORDER_CONSTANT, value=0)
    for index in range(orientations):
        angle = 180.0 * index / orientations
        closed = cv2.morphologyEx(src, cv2.MORPH_CLOSE, line_kernel(length, angle))[length:-length, length:-length].astype(bool)
        gap = closed & ~blocked
        axis = np.array([np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))])
        for component, origin, _ in components_cropped(gap, min_area=scale.px(0.3) ** 2):
            yield axis, component, origin


def _opening_from_component(
    component: np.ndarray,
    blocked: np.ndarray,
    scale: Scale,
    min_width_m: float,
    max_width_m: float,
    ids,
    sources: tuple[str, ...],
    confidence: float,
    check_contacts: bool = True,
    axis: np.ndarray | None = None,
    origin: tuple[int, int] = (0, 0),
) -> Opening | None:
    # `component` is a tight crop located at `origin`; work in a padded window around it
    pad = max(3, int(round(scale.px(0.8))))
    ch, cw = component.shape
    y0, y1 = max(0, origin[1] - pad), min(blocked.shape[0], origin[1] + ch + pad)
    x0, x1 = max(0, origin[0] - pad), min(blocked.shape[1], origin[0] + cw + pad)
    window = np.zeros((y1 - y0, x1 - x0), dtype=bool)
    window[origin[1] - y0 : origin[1] - y0 + ch, origin[0] - x0 : origin[0] - x0 + cw] = component
    component = window
    blocked = blocked[y0:y1, x0:x1]
    ys, xs = np.nonzero(component)
    if xs.size == 0:
        return None
    points = np.column_stack((xs, ys))
    center, long_side, short_side, box_axis, box = oriented_box(points)
    if axis is None:
        axis = box_axis
    if check_contacts:
        refined = _refine_gap(component, blocked, axis, scale)
        if refined is None:
            return None
        center, long_side, short_side, box = refined
    center = (center[0] + x0, center[1] + y0)
    box = box + np.array([x0, y0], dtype=float)
    if not (scale.px(min_width_m) <= long_side <= scale.px(max_width_m)):
        return None
    if short_side > scale.px(MAX_WALL_M) or short_side < 1:
        return None
    normal = np.array([-axis[1], axis[0]])
    polygon = Polygon(box.tolist())
    if not polygon.is_valid or polygon.area <= 0:
        return None
    return Opening(
        id=f"o{next(ids)}",
        polygon=polygon,
        center=center,
        axis=segment(center, axis, long_side),
        normal=(float(normal[0]), float(normal[1])),
        width_px=long_side,
        kind="door",
        confidence=confidence,
        sources=sources,
    )


def _refine_gap(component: np.ndarray, blocked: np.ndarray, axis: np.ndarray, scale: Scale):
    """Measure a doorway from the two wall faces it spans.

    The union of oriented closings inflates the filled region (diagonal kernels bridge the
    corners too), so the width is taken as the distance between the wall end faces and
    the depth as the extent of those faces across the wall.
    """
    if not _has_two_contacts(component, blocked, axis):
        return None
    ys, xs = np.nonzero(component)
    projection = xs * axis[0] + ys * axis[1]
    lo, hi = projection.min(), projection.max()
    span = hi - lo
    ring = cv2.dilate(component.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & blocked
    cy, cx = np.nonzero(ring)
    along = cx * axis[0] + cy * axis[1]
    normal = np.array([-axis[1], axis[0]])
    across = cx * normal[0] + cy * normal[1]
    lo_face = along[along <= lo + span * 0.2]
    hi_face = along[along >= hi - span * 0.2]
    if lo_face.size == 0 or hi_face.size == 0:
        return None
    a, b = float(lo_face.max()), float(hi_face.min())
    if b - a < 2:
        return None
    faces = across[(along <= lo + span * 0.2) | (along >= hi - span * 0.2)]
    depth = max(2.0, float(np.percentile(faces, 98) - np.percentile(faces, 2)) + 2.0)
    mid_along = (a + b) / 2.0
    mid_across = float(np.median(faces))
    center = (mid_along * axis[0] + mid_across * normal[0], mid_along * axis[1] + mid_across * normal[1])
    width = b - a
    # A doorway sits inside a wall: behind at least one of its jambs the wall continues
    # along the axis. A band bridging two facing parallel walls (a corridor filled by a
    # perpendicular or slanted kernel) only has one wall thickness behind each face.
    # Both jamb faces of a doorway are perpendicular to the axis; the two legs of a
    # filled concave corner and the walls of a slanted corridor band are not.
    pixels = np.column_stack((cx, cy))
    for face_pixels in (pixels[np.abs(along - a) <= 2.5], pixels[np.abs(along - b) <= 2.5]):
        direction = _principal_direction(face_pixels)
        if direction is not None and abs(float(direction @ axis)) > 0.5:
            return None
    needed = max(scale.px(0.35), 1.2 * depth)
    behind = [
        _wall_run(blocked, a, mid_across, -1, axis, normal, scale),
        _wall_run(blocked, b, mid_across, 1, axis, normal, scale),
    ]
    if max(behind) < needed:
        return None
    box = np.array(
        [
            center + axis * (width / 2) + normal * (depth / 2),
            center - axis * (width / 2) + normal * (depth / 2),
            center - axis * (width / 2) - normal * (depth / 2),
            center + axis * (width / 2) - normal * (depth / 2),
        ]
    )
    return (float(center[0]), float(center[1])), float(width), float(depth), box


def _principal_direction(pixels: np.ndarray) -> np.ndarray | None:
    if len(pixels) < 3:
        return None
    pts = pixels.astype(float)
    centered = pts - pts.mean(axis=0)
    if np.allclose(centered, 0):
        return None
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    return vt[0]


def _wall_run(blocked: np.ndarray, face: float, mid_across: float, direction: int, axis: np.ndarray, normal: np.ndarray, scale: Scale) -> float:
    """Length of continuous wall material behind a face, measured along the axis."""
    h, w = blocked.shape
    step = max(1.0, scale.px(0.05))
    run = 0.0
    for k in range(1, 40):
        along = face + direction * k * step
        x = along * axis[0] + mid_across * normal[0]
        y = along * axis[1] + mid_across * normal[1]
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= yi < h and 0 <= xi < w):
            break
        if not blocked[max(0, yi - 1) : yi + 2, max(0, xi - 1) : xi + 2].any():
            break
        run = k * step
    return run


def _has_two_contacts(component: np.ndarray, blocked: np.ndarray, axis: np.ndarray) -> bool:
    """A doorway gap ends on wall material at *both* ends of its long axis.

    Concave corners filled by the closing touch the wall along one side only, so the
    wall contact never reaches both ends of the long axis and they are rejected here.
    """
    ys, xs = np.nonzero(component)
    projection = xs * axis[0] + ys * axis[1]
    lo, hi = projection.min(), projection.max()
    span = hi - lo
    if span <= 0:
        return False
    ring = cv2.dilate(component.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & blocked
    cy, cx = np.nonzero(ring)
    if cx.size == 0:
        return False
    contact = cx * axis[0] + cy * axis[1]
    near_lo = (contact <= lo + span * 0.2).any()
    near_hi = (contact >= hi - span * 0.2).any()
    # ... and the wall must not run along the whole long side (that is a corner or niche).
    along = np.count_nonzero((contact > lo + span * 0.25) & (contact < hi - span * 0.25))
    return bool(near_lo and near_hi and along <= 0.6 * cx.size)


def swing_evidence(thin: np.ndarray, center: tuple[float, float], normal: tuple[float, float], width_px: float, scale: Scale) -> float:
    """How much thin line-work (a door leaf and its swing arc) sits next to an opening.

    Returns the best of both sides as a fraction of the expected arc length. Windows have
    nothing drawn on either side; doors have a quarter circle of roughly 1.6 * width.
    """
    h, w = thin.shape
    best = 0.0
    side = max(4, int(round(width_px)))
    half = side / 2.0
    for sign in (1, -1):
        cx = center[0] + sign * normal[0] * (half + scale.px(0.1))
        cy = center[1] + sign * normal[1] * (half + scale.px(0.1))
        x0, x1 = int(max(0, cx - half)), int(min(w, cx + half))
        y0, y1 = int(max(0, cy - half)), int(min(h, cy + half))
        if x1 <= x0 or y1 <= y0:
            continue
        count = float(np.count_nonzero(thin[y0:y1, x0:x1]))
        best = max(best, count / max(1.6 * width_px, 1.0))
    return best if best >= 0.5 else 0.0
