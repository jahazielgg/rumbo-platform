"""Deterministic wall perception for line-drawing floorplans.

Walls are the thick dark strokes of a plan; text, furniture and dimension lines are thin.
A morphological opening whose kernel is a fraction of the dominant stroke thickness
keeps exactly the thick structure, including free-standing columns that a downscaled
CNN loses. This backend is the fallback when no ML model is available and the
supplementary source used to recover small structural elements.
"""
from __future__ import annotations

import numpy as np
import cv2
from skimage.morphology import skeletonize

from ..contracts import RasterInput, Scale, StructuralMasks


def dark_mask(image: np.ndarray, max_threshold: int = 110) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    otsu, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = int(min(otsu, max_threshold))
    return gray < max(threshold, 40)


def estimate_stroke_thickness(mask: np.ndarray, minimum: float = 3.0) -> float:
    """Area-weighted dominant stroke thickness in pixels."""
    if not mask.any():
        return minimum
    distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    skeleton = skeletonize(mask)
    values = 2.0 * distance[skeleton]
    values = values[values >= minimum]
    if values.size == 0:
        return minimum
    bins = np.arange(minimum, values.max() + 2, 1.0)
    histogram, edges = np.histogram(values, bins=bins)
    weighted = histogram * edges[:-1]  # thicker strokes carry more area
    index = int(np.argmax(weighted))
    return float(edges[index] + 0.5)


def thick_structure(mask: np.ndarray, thickness: float, ratio: float = 0.6) -> np.ndarray:
    size = max(3, int(round(thickness * ratio)))
    if size % 2 == 0:
        size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    opened = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
    return opened.astype(bool)


def remove_small(mask: np.ndarray, min_area: float) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    keep = np.zeros_like(mask, dtype=bool)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= min_area:
            keep[labels == index] = True
    return keep


class ClassicalPerceiver:
    name = "classical-morphology"

    def perceive(self, source: RasterInput, scale: Scale | None) -> StructuralMasks:
        dark = dark_mask(source.image)
        thickness = estimate_stroke_thickness(dark)
        if scale is not None:
            # Never treat strokes thinner than ~8 cm as walls when the scale is known.
            thickness = max(thickness, scale.px(0.08))
        walls = thick_structure(dark, thickness, ratio=0.5)
        # keep short wall stubs between windows: they matter for the building envelope
        walls = remove_small(walls, min_area=thickness * thickness * 0.5)
        thin = dark & ~cv2.dilate(walls.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        empty = np.zeros_like(walls, dtype=bool)
        return StructuralMasks(wall=walls, door=empty, window=empty.copy(), thin=thin, backend=self.name)
