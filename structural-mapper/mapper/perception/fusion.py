"""Combine several perception sources into one structural mask set.

Policy (documented so administrators can reason about proposals):
- vector strokes are exact: always kept;
- classical thick strokes are kept: they are the drawn structure of a line plan;
- ML wall components are kept when they agree with the drawn structure (overlap) or
  when the network is confident about them (they cover walls the classical detector
  cannot see, e.g. light-grey or hatched walls), never as isolated speckle;
- ML windows are kept only when attached to an accepted wall;
- ML door pixels are evidence for the geometric opening detector, not walls.
"""
from __future__ import annotations

import cv2
import numpy as np

from ..contracts import Scale, StructuralMasks


def fuse(primary: StructuralMasks | None, classical: StructuralMasks | None, vector: StructuralMasks | None, scale: Scale) -> StructuralMasks:
    shape = next(m.wall.shape for m in (primary, classical, vector) if m is not None)
    wall = np.zeros(shape, dtype=bool)
    door = np.zeros(shape, dtype=bool)
    window = np.zeros(shape, dtype=bool)
    backends: list[str] = []

    if vector is not None:
        wall |= vector.wall
        backends.append(vector.backend)
    drawn = wall.copy()
    if classical is not None:
        if drawn.any():
            wall |= _accept_classical(classical.wall, drawn, scale)
        else:
            wall |= classical.wall
        drawn = wall.copy()
        backends.append(classical.backend)
    if primary is not None:
        wall |= _accept_ml_walls(primary, drawn, scale)
        door |= primary.door
        window |= _attached(primary.window, wall, scale)
        backends.append(primary.backend)

    # Perception never produces a door where a wall exists; walls win.
    door &= ~wall
    window &= ~wall
    thin = classical.thin if classical is not None else None
    if thin is not None:
        thin = thin & ~wall
    return StructuralMasks(
        wall=wall,
        door=door,
        window=window,
        wall_probability=primary.wall_probability if primary else None,
        thin=thin,
        backend="+".join(backends),
    )


def _accept_classical(candidate: np.ndarray, accepted_walls: np.ndarray, scale: Scale) -> np.ndarray:
    if not accepted_walls.any():
        return candidate
    count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate.astype(np.uint8), 8)
    result = np.zeros_like(candidate, dtype=bool)
    column_area = scale.px(0.9) ** 2
    for index in range(1, count):
        component = labels == index
        area = float(stats[index, cv2.CC_STAT_AREA])
        w, h = stats[index, cv2.CC_STAT_WIDTH], stats[index, cv2.CC_STAT_HEIGHT]
        overlap = float(np.count_nonzero(component & accepted_walls)) / max(area, 1.0)
        compact = area <= column_area and max(w, h) / max(1, min(w, h)) <= 3.0
        if overlap >= 0.2 or compact:
            result |= component
    return result


def _accept_ml_walls(primary: StructuralMasks, drawn: np.ndarray, scale: Scale) -> np.ndarray:
    """Keep ML wall components that agree with drawn structure or are confidently predicted."""
    if not drawn.any():
        return primary.wall
    count, labels, stats, _ = cv2.connectedComponentsWithStats(primary.wall.astype(np.uint8), 8)
    result = np.zeros_like(primary.wall, dtype=bool)
    min_area = scale.px(0.15) ** 2
    for index in range(1, count):
        area = float(stats[index, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        component = labels == index
        overlap = float(np.count_nonzero(component & drawn)) / area
        confident = False
        if primary.wall_probability is not None:
            confident = float(primary.wall_probability[component].mean()) >= 0.85 and area >= scale.px(0.4) ** 2
        if overlap >= 0.3 or confident:
            result |= component
    return result


def _attached(mask: np.ndarray, wall: np.ndarray, scale: Scale) -> np.ndarray:
    """Keep components of `mask` that touch an accepted wall and are not speckle."""
    if not mask.any():
        return mask
    grown = cv2.dilate(wall.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    result = np.zeros_like(mask, dtype=bool)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] < scale.px(0.25) ** 2:
            continue
        component = labels == index
        if (component & grown).any():
            result |= component
    return result
