from __future__ import annotations

from pathlib import Path

from app.bootstrap.sample_data import SAMPLE_FILENAME


SAMPLE_ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets"


def ensure_sample_floorplan_asset(upload_path: Path) -> Path:
    """Ensure the bundled sample floorplan exists in persistent upload storage.

    PostgreSQL and uploads live in independent Docker volumes. A persisted sample
    database row therefore does not guarantee that its image is still present. Keep
    the bundled tutorial asset self-healing without recreating or modifying the user's
    spatial model, navigation graph, or positioning configuration.
    """
    source = SAMPLE_ASSET_ROOT / SAMPLE_FILENAME
    target = upload_path / SAMPLE_FILENAME

    upload_path.mkdir(parents=True, exist_ok=True)
    expected = source.read_bytes()
    if not target.is_file() or target.read_bytes() != expected:
        target.write_bytes(expected)

    return target
