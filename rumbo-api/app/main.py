from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.bootstrap.sample_asset import ensure_sample_floorplan_asset
from app.bootstrap.sample_data import ensure_sample_data
from app.floorplans.presentation.router import router as floorplans_router
from app.infrastructure.database import SessionLocal
from app.infrastructure.settings import get_settings
from app.modeling.presentation.router import router as modeling_router
from app.navigation.presentation.router import router as navigation_router
from app.positioning.presentation.router import router as positioning_router

settings = get_settings()
settings.upload_path.mkdir(parents=True, exist_ok=True)


def _asset_media_type(path: Path) -> str:
    """Infer an uploaded asset's media type from its contents, not its extension."""
    with path.open("rb") as file:
        head = file.read(512)

    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"%PDF-"):
        return "application/pdf"

    stripped = head.lstrip()
    if stripped.startswith(b"<svg") or (stripped.startswith(b"<?xml") and b"<svg" in stripped):
        return "image/svg+xml"

    return "application/octet-stream"


def _resolve_upload(filename: str) -> Path:
    root = settings.upload_path.resolve()
    candidate = (root / filename).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return candidate


def _asset_cors_headers(request: Request) -> dict[str, str]:
    headers = {
        "Cache-Control": "no-store, max-age=0",
        "Vary": "Origin",
    }
    origin = request.headers.get("origin")
    if origin and origin in settings.allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return headers


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.seed_sample_data:
        ensure_sample_floorplan_asset(settings.upload_path)
        with SessionLocal() as db:
            ensure_sample_data(db, settings)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description="Rumbo modular monolith API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/uploads/{filename:path}", include_in_schema=False)
def uploaded_asset(filename: str, request: Request):
    path = _resolve_upload(filename)
    return FileResponse(
        path,
        media_type=_asset_media_type(path),
        headers=_asset_cors_headers(request),
    )


app.include_router(floorplans_router, prefix=settings.api_prefix)
app.include_router(modeling_router, prefix=settings.api_prefix)
app.include_router(navigation_router, prefix=settings.api_prefix)
app.include_router(positioning_router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "rumbo-api", "version": "0.4.0"}
