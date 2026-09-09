"""Rumbo Structural Mapper service (v3).

Thin HTTP layer over `mapper.pipeline`. The ML backend (BuildingCV) is optional: when
its weights or PyTorch are missing the service still runs with the deterministic
vector/classical perception, so the geometry pipeline can be tested anywhere.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from mapper.ingest.decode import DecodeError
from mapper.pipeline import PARSER_VERSION, MapperOptions, Pipeline, scene_to_payload

MAX_BYTES = 32 * 1024 * 1024
log = logging.getLogger("structural-mapper")


def _load_ml():
    if os.getenv("STRUCTURAL_MAPPER_DISABLE_ML", "").lower() in ("1", "true", "yes"):
        return None
    try:
        from mapper.perception.buildingcv import BuildingCvPerceiver

        return BuildingCvPerceiver(os.getenv("BUILDINGCV_RUN_DIR"), os.getenv("BUILDINGCV_DEVICE", "cpu"))
    except Exception as exc:  # pragma: no cover - depends on the runtime image
        log.warning("ML perception unavailable, running deterministic backends only: %s", exc)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    ml = _load_ml()
    app.state.pipeline = Pipeline(ml=ml)
    app.state.ml_backend = ml.name if ml is not None else None
    yield


app = FastAPI(title="Rumbo Structural Mapper", version="3.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "parser": "rumbo-structural-mapper",
        "parser_version": PARSER_VERSION,
        "ml_backend": app.state.ml_backend,
        "backends": [b for b in ("vector-strokes", "classical-morphology", app.state.ml_backend) if b],
    }


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    pixels_per_meter: float | None = Form(default=None),
    raster_scale: float = Form(default=2.0),
    use_ml: bool = Form(default=True),
) -> dict:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Plano vacío.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Plano demasiado grande para análisis.")
    options = MapperOptions(pixels_per_meter=pixels_per_meter, raster_scale=raster_scale, use_ml=use_ml)
    try:
        scene = app.state.pipeline.run_bytes(raw, file.content_type, options)
    except DecodeError as exc:
        raise HTTPException(status_code=422, detail=f"No se pudo decodificar el plano: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return scene_to_payload(scene)
