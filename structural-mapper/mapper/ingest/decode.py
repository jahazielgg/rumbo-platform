"""Turn uploaded bytes into a `RasterInput`.

Vector documents (PDF, SVG) are rasterized *and* parsed: the exact stroke geometry
becomes a high-confidence wall mask and the page text becomes room labels. Raster
images go through perception only.
"""
from __future__ import annotations

import base64
import binascii
import re
from io import BytesIO

import numpy as np
from PIL import Image

from ..contracts import RasterInput
from .vector import VectorDocument, parse_vector_document

MAX_SIDE = 4096
_BASE64_HEAD = re.compile(rb"^\s*(?:data:[a-z/+.-]+;base64,)?([A-Za-z0-9+/=\r\n]+)$")


class DecodeError(ValueError):
    pass


def _maybe_base64(raw: bytes) -> bytes:
    """Some tools save images as base64 text; be forgiving."""
    head = raw[:64].lstrip()
    if head.startswith((b"\x89PNG", b"\xff\xd8", b"%PDF", b"<", b"GIF8", b"RIFF")):
        return raw
    match = _BASE64_HEAD.match(raw[:4_000_000])
    if not match:
        return raw
    payload = re.sub(rb"\s+", b"", match.group(1))
    payload += b"=" * (-len(payload) % 4)
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return raw
    return decoded if decoded.startswith((b"\x89PNG", b"\xff\xd8", b"%PDF", b"GIF8", b"RIFF")) else raw


def _is_svg(raw: bytes) -> bool:
    head = raw[:512].lstrip().lower()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head)


def _fit(image: Image.Image) -> Image.Image:
    if max(image.size) <= MAX_SIDE:
        return image
    factor = MAX_SIDE / max(image.size)
    return image.resize((max(1, round(image.width * factor)), max(1, round(image.height * factor))), Image.Resampling.LANCZOS)


def decode(raw: bytes, content_type: str | None = None, *, raster_scale: float = 2.0) -> RasterInput:
    """Decode bytes into an RGB raster plus optional vector layers.

    `raster_scale` is the zoom applied to vector pages. The API renders PDF previews with
    the same zoom, so graph coordinates line up with what the editor displays.
    """
    raw = _maybe_base64(raw)
    if not raw:
        raise DecodeError("empty document")

    if raw.startswith(b"%PDF") or content_type == "application/pdf":
        return _from_vector(parse_vector_document(raw, "pdf", raster_scale), "pdf")
    if _is_svg(raw) or content_type == "image/svg+xml":
        return _from_vector(parse_vector_document(raw, "svg", raster_scale), "svg")

    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except Exception as exc:  # pragma: no cover - PIL specific
        raise DecodeError("unsupported or corrupt image") from exc
    image = _fit(image.convert("RGB"))
    return RasterInput(image=np.asarray(image, dtype=np.uint8).copy(), source_kind="raster")


def _from_vector(document: VectorDocument, kind: str) -> RasterInput:
    return RasterInput(
        image=document.image,
        labels=document.labels,
        vector_walls=document.wall_mask if document.wall_mask is not None and document.wall_mask.any() else None,
        vector_scale=document.pixels_per_meter,
        source_kind="pdf-vector" if kind == "pdf" and document.has_vectors else ("svg-vector" if kind == "svg" else "pdf-raster"),
    )
