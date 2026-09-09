"""Vector document parsing with PyMuPDF.

Architectural PDFs exported from CAD/BIM keep walls as thick strokes or dark filled
polygons and room names as text. Reading that geometry directly is exact, resolution
independent and free of ML errors, so it is the preferred perception source whenever
it exists. Raster-only PDFs (scans) simply return `has_vectors=False`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import cv2
import numpy as np
import pymupdf

from ..contracts import TextLabel

DARK_LUMINANCE = 0.55
LIGHT_LUMINANCE = 0.85
MIN_WALL_STROKE_PT = 2.0
MAX_FILL_FRACTION = 0.25  # filled shapes larger than this fraction of the page are backgrounds
_SCALE_TEXT = re.compile(r"(?:escala|scale)\s*[:=]?\s*1\s*[:/]\s*(\d{2,4})", re.IGNORECASE)


@dataclass(slots=True)
class VectorDocument:
    image: np.ndarray
    wall_mask: np.ndarray | None
    labels: list[TextLabel] = field(default_factory=list)
    has_vectors: bool = False
    pixels_per_meter: float | None = None


def _luminance(color) -> float | None:
    if color is None:
        return None
    r, g, b = (float(c) for c in color[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _open(raw: bytes, kind: str) -> pymupdf.Document:
    if kind == "svg":
        svg = pymupdf.open(stream=raw, filetype="svg")
        return pymupdf.open("pdf", svg.convert_to_pdf())
    return pymupdf.open(stream=raw, filetype="pdf")


def parse_vector_document(raw: bytes, kind: str, raster_scale: float = 2.0) -> VectorDocument:
    document = _open(raw, kind)
    if document.page_count == 0:
        raise ValueError("document has no pages")
    page = document.load_page(0)
    matrix = pymupdf.Matrix(raster_scale, raster_scale)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)[:, :, :3].copy()

    drawings = page.get_drawings()
    page_area = float(page.rect.width * page.rect.height)
    mask = np.zeros((pixmap.height, pixmap.width), dtype=np.uint8)
    stroke_threshold = _wall_stroke_threshold(drawings)
    drew_anything = False

    for path in drawings:
        stroke_lum = _luminance(path.get("color"))
        fill_lum = _luminance(path.get("fill"))
        width_pt = float(path.get("width") or 0.0)
        rect = path.get("rect")
        rect_area = float(rect.width * rect.height) if rect is not None else 0.0
        polygon = _path_points(path)

        # Dark filled shapes that are not page backgrounds are walls/columns.
        if fill_lum is not None and fill_lum < DARK_LUMINANCE and rect_area < page_area * MAX_FILL_FRACTION and len(polygon) >= 3:
            cv2.fillPoly(mask, [_to_px(polygon, matrix)], 1)
            drew_anything = True

        if stroke_lum is None or width_pt < MIN_WALL_STROKE_PT:
            continue
        thickness = max(1, int(round(width_pt * raster_scale)))
        if stroke_lum < DARK_LUMINANCE and width_pt >= stroke_threshold:
            _stroke(mask, path, matrix, thickness, 1)
            drew_anything = True
        elif stroke_lum > LIGHT_LUMINANCE and width_pt >= stroke_threshold * 0.5:
            # Light strokes drawn over walls are erasers (door openings, cut-outs).
            _stroke(mask, path, matrix, thickness, 0)

    labels = _labels(page, matrix)
    return VectorDocument(
        image=image,
        wall_mask=mask.astype(bool) if drew_anything else None,
        labels=labels,
        has_vectors=bool(drawings),
        pixels_per_meter=_scale_from_text(page, raster_scale, labels),
    )


def _wall_stroke_threshold(drawings: list[dict]) -> float:
    """Walls are the thickest *widely used* dark stroke family on the page."""
    weighted: list[tuple[float, float]] = []
    for path in drawings:
        lum = _luminance(path.get("color"))
        width = float(path.get("width") or 0.0)
        if lum is None or lum >= DARK_LUMINANCE or width < MIN_WALL_STROKE_PT:
            continue
        length = sum(_item_length(item) for item in path.get("items", []))
        if length > 0:
            weighted.append((width, length))
    if not weighted:
        return MIN_WALL_STROKE_PT
    weighted.sort()
    total = sum(length for _, length in weighted)
    running = 0.0
    p90 = weighted[-1][0]
    for width, length in weighted:
        running += length
        if running >= total * 0.9:
            p90 = width
            break
    return max(MIN_WALL_STROKE_PT, p90 * 0.5)


def _item_length(item) -> float:
    kind = item[0]
    if kind == "l":
        return float(item[1].distance_to(item[2]))
    if kind == "re":
        r = item[1]
        return float(2 * (r.width + r.height))
    if kind == "qu":
        q = item[1]
        return float(q.ul.distance_to(q.ur) * 2 + q.ul.distance_to(q.ll) * 2)
    if kind == "c":
        return float(item[1].distance_to(item[4]))
    return 0.0


def _path_points(path: dict) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in path.get("items", []):
        kind = item[0]
        if kind == "l":
            points.extend([(item[1].x, item[1].y), (item[2].x, item[2].y)])
        elif kind == "re":
            r = item[1]
            points.extend([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
        elif kind == "qu":
            q = item[1]
            points.extend([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)])
        elif kind == "c":
            points.extend([(item[1].x, item[1].y), (item[4].x, item[4].y)])
    return points


def _to_px(points: list[tuple[float, float]], matrix: pymupdf.Matrix) -> np.ndarray:
    return np.array([[int(round(x * matrix.a)), int(round(y * matrix.d))] for x, y in points], dtype=np.int32)


def _stroke(mask: np.ndarray, path: dict, matrix: pymupdf.Matrix, thickness: int, value: int) -> None:
    for item in path.get("items", []):
        kind = item[0]
        if kind == "l":
            a = _to_px([(item[1].x, item[1].y)], matrix)[0]
            b = _to_px([(item[2].x, item[2].y)], matrix)[0]
            cv2.line(mask, tuple(int(v) for v in a), tuple(int(v) for v in b), value, thickness, cv2.LINE_8)
        elif kind in ("re", "qu"):
            pts = _to_px(_path_points({"items": [item]}), matrix)
            cv2.polylines(mask, [pts], True, value, thickness, cv2.LINE_8)
        elif kind == "c":
            pts = _bezier(item, matrix)
            cv2.polylines(mask, [pts], False, value, thickness, cv2.LINE_8)


def _bezier(item, matrix: pymupdf.Matrix, steps: int = 12) -> np.ndarray:
    p0, p1, p2, p3 = item[1], item[2], item[3], item[4]
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 3 * p0.x + 3 * (1 - t) ** 2 * t * p1.x + 3 * (1 - t) * t**2 * p2.x + t**3 * p3.x
        y = (1 - t) ** 3 * p0.y + 3 * (1 - t) ** 2 * t * p1.y + 3 * (1 - t) * t**2 * p2.y + t**3 * p3.y
        points.append((x, y))
    return _to_px(points, matrix)


def _labels(page: pymupdf.Page, matrix: pymupdf.Matrix) -> list[TextLabel]:
    labels: list[TextLabel] = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
        text = " ".join(str(text).split())
        if not text:
            continue
        labels.append(TextLabel(text=text, position=(((x0 + x1) / 2) * matrix.a, ((y0 + y1) / 2) * matrix.d)))
    return labels


def _scale_from_text(page: pymupdf.Page, raster_scale: float, labels: list[TextLabel]) -> float | None:
    """`Escala 1:100` on a title block gives an exact pixel/metre ratio for PDF pages."""
    for label in labels:
        match = _SCALE_TEXT.search(label.text)
        if match:
            denominator = float(match.group(1))
            points_per_meter = 1000.0 / 25.4 * 72.0 / denominator  # 1 m at 1:den in PDF points
            return points_per_meter * raster_scale
    return None
