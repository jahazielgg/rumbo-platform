"""Raster <-> vector helpers shared by the deterministic stages."""
from __future__ import annotations

from typing import Iterable

import cv2
import numpy as np
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid


def mask_to_polygons(mask: np.ndarray, simplify_px: float = 1.0, min_area: float = 4.0) -> list[Polygon]:
    """Vectorize a boolean mask into valid polygons with holes."""
    binary = mask.astype(np.uint8)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    hierarchy = hierarchy[0]
    polygons: list[Polygon] = []
    for index, contour in enumerate(contours):
        if hierarchy[index][3] != -1:  # holes are attached to their parent below
            continue
        outer = contour.reshape(-1, 2).astype(float)
        if len(outer) < 3 or cv2.contourArea(contour) < min_area:
            continue
        holes = []
        child = hierarchy[index][2]
        while child != -1:
            ring = contours[child].reshape(-1, 2).astype(float)
            if len(ring) >= 3 and cv2.contourArea(contours[child]) >= min_area:
                holes.append(ring)
            child = hierarchy[child][0]
        polygon = Polygon(outer, holes)
        if simplify_px > 0:
            polygon = polygon.simplify(simplify_px, preserve_topology=True)
        polygons.extend(as_polygons(make_valid(polygon)))
    return [p for p in polygons if p.area >= min_area]


def as_polygons(geometry: BaseGeometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    if hasattr(geometry, "geoms"):
        result: list[Polygon] = []
        for part in geometry.geoms:
            result.extend(as_polygons(part))
        return result
    return []


def rasterize(polygons: Iterable[BaseGeometry], shape: tuple[int, int], value: int = 1, dilate_px: int = 0) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    for geometry in polygons:
        for polygon in as_polygons(geometry):
            outer = np.round(np.asarray(polygon.exterior.coords)).astype(np.int32)
            cv2.fillPoly(mask, [outer], value)
            for hole in polygon.interiors:
                cv2.fillPoly(mask, [np.round(np.asarray(hole.coords)).astype(np.int32)], 0)
    if dilate_px > 0:
        mask = cv2.dilate(mask, np.ones((2 * dilate_px + 1, 2 * dilate_px + 1), np.uint8))
    return mask.astype(bool)


def oriented_box(points: np.ndarray) -> tuple[tuple[float, float], float, float, np.ndarray, np.ndarray]:
    """Return (center, long, short, long_axis_unit, box_points) for a point cloud."""
    (cx, cy), (w, h), angle = cv2.minAreaRect(points.astype(np.float32))
    box = cv2.boxPoints(((cx, cy), (w, h), angle))
    rad = np.deg2rad(angle)
    axis = np.array([np.cos(rad), np.sin(rad)])
    if h > w:
        axis = np.array([-axis[1], axis[0]])
    long_side, short_side = max(w, h), min(w, h)
    return (float(cx), float(cy)), float(long_side), float(short_side), axis, box


def segment(center: tuple[float, float], axis: np.ndarray, length: float) -> LineString:
    half = axis * (length / 2.0)
    return LineString([(center[0] - half[0], center[1] - half[1]), (center[0] + half[0], center[1] + half[1])])


def components(mask: np.ndarray, min_area: float = 1.0):
    """Yield (label_mask, stats) for each connected component above `min_area`."""
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= min_area:
            yield labels == index, stats[index], centroids[index]


def line_kernel(length: int, angle_deg: float) -> np.ndarray:
    kernel = np.zeros((length, length), np.uint8)
    c = (length - 1) / 2.0
    rad = np.deg2rad(angle_deg)
    dx, dy = np.cos(rad) * c, np.sin(rad) * c
    cv2.line(kernel, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
    return kernel


def line_closing(mask: np.ndarray, length_px: float, orientations: int = 12) -> np.ndarray:
    """Union of morphological closings with line kernels at several orientations.

    Unlike a disc, a line kernel bridges a gap of up to `length_px` in a *thin* wall that
    runs parallel to it, which is exactly what doorways and cropped corridor ends look like.
    """
    length = max(3, int(round(length_px)))
    if length % 2 == 0:
        length += 1
    # pad with free space: OpenCV's erosion treats out-of-image pixels as foreground, which
    # would seal every margin narrower than the kernel against the image border
    src = cv2.copyMakeBorder(mask.astype(np.uint8), length, length, length, length, cv2.BORDER_CONSTANT, value=0)
    out = np.zeros_like(src)
    for index in range(orientations):
        out |= cv2.morphologyEx(src, cv2.MORPH_CLOSE, line_kernel(length, 180.0 * index / orientations))
    return out[length:-length, length:-length].astype(bool)


def components_cropped(mask: np.ndarray, min_area: float = 1.0):
    """Yield (crop_mask, (x0, y0), stats) per connected component; crops avoid full-frame work."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] < min_area:
            continue
        x, y, w, h = (int(stats[index, i]) for i in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        yield labels[y : y + h, x : x + w] == index, (x, y), stats[index]
