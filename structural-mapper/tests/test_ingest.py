import base64

import numpy as np

from mapper.ingest.decode import decode


def test_decode_svg_extracts_vector_walls_and_labels(synthetic_case):
    case, svg, _ = synthetic_case
    source = decode(svg, "image/svg+xml", raster_scale=2.0)
    assert source.source_kind == "svg-vector"
    assert source.vector_walls is not None and source.vector_walls.any()
    assert source.width == round(case["canvas_meters"]["width"] * 28 * 2)
    assert {label.text for label in source.labels} >= {"Consultorio"}


def test_decode_accepts_base64_encoded_images():
    from PIL import Image
    from io import BytesIO

    buffer = BytesIO()
    Image.fromarray(np.full((40, 60, 3), 255, dtype=np.uint8)).save(buffer, format="PNG")
    payload = base64.b64encode(buffer.getvalue())
    source = decode(payload, "image/png")
    assert source.image.shape == (40, 60, 3)
    assert source.source_kind == "raster"


def test_decode_pdf_uses_page_geometry(synthetic_case):
    import pymupdf

    _, svg, _ = synthetic_case
    pdf = pymupdf.open("pdf", pymupdf.open(stream=svg, filetype="svg").convert_to_pdf()).tobytes()
    source = decode(pdf, "application/pdf", raster_scale=1.0)
    assert source.source_kind == "pdf-vector"
    assert source.vector_walls is not None
