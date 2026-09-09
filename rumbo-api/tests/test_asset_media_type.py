from pathlib import Path

from starlette.requests import Request

from app.main import _asset_cors_headers, _asset_media_type


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _request(origin: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/uploads/floorplan.png",
            "raw_path": b"/uploads/floorplan.png",
            "query_string": b"",
            "headers": [(b"origin", origin.encode())],
            "client": ("127.0.0.1", 12345),
            "server": ("localhost", 8000),
        }
    )


def test_detects_png_even_with_jpg_extension(tmp_path: Path):
    path = _write(tmp_path, "floorplan.jpg", b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    assert _asset_media_type(path) == "image/png"


def test_detects_jpeg(tmp_path: Path):
    path = _write(tmp_path, "floorplan.jpg", b"\xff\xd8\xff" + b"0" * 16)
    assert _asset_media_type(path) == "image/jpeg"


def test_detects_pdf(tmp_path: Path):
    path = _write(tmp_path, "floorplan.pdf", b"%PDF-1.7\n")
    assert _asset_media_type(path) == "application/pdf"


def test_detects_svg(tmp_path: Path):
    path = _write(tmp_path, "floorplan.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    assert _asset_media_type(path) == "image/svg+xml"


def test_upload_headers_allow_configured_web_origin():
    headers = _asset_cors_headers(_request("http://localhost:5173"))
    assert headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert headers["Access-Control-Allow-Credentials"] == "true"
    assert headers["Cache-Control"] == "no-store, max-age=0"
    assert headers["Vary"] == "Origin"


def test_upload_headers_do_not_reflect_unknown_origin():
    headers = _asset_cors_headers(_request("https://example.com"))
    assert "Access-Control-Allow-Origin" not in headers
