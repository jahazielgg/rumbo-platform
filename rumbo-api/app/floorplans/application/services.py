from pathlib import Path
from uuid import UUID

from app.shared_kernel.errors import NotFoundError, ValidationError

from ..domain.entities import Floorplan
from ..domain.repositories import FloorplanRepository
from .ports import FloorplanStorage


ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf"}


class FloorplanService:
    def __init__(self, repository: FloorplanRepository, storage: FloorplanStorage, max_upload_mb: int = 20):
        self.repository = repository
        self.storage = storage
        self.max_upload_bytes = max_upload_mb * 1024 * 1024

    def create(
        self,
        *,
        name: str,
        building_name: str,
        floor_label: str,
        original_filename: str,
        media_type: str,
        content: bytes,
    ) -> Floorplan:
        suffix = Path(original_filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ValidationError("Formato no soportado. Usa PNG, JPG, WEBP, SVG o PDF.")
        if not content:
            raise ValidationError("El archivo está vacío.")
        if len(content) > self.max_upload_bytes:
            raise ValidationError(f"El archivo supera el límite de {self.max_upload_bytes // (1024 * 1024)} MB.")
        if not name.strip() or not building_name.strip() or not floor_label.strip():
            raise ValidationError("Nombre, edificio y piso son obligatorios.")

        stored_filename = self.storage.save(content=content, suffix=suffix)
        entity = Floorplan.create(
            name=name,
            building_name=building_name,
            floor_label=floor_label,
            original_filename=original_filename,
            stored_filename=stored_filename,
            media_type=media_type or "application/octet-stream",
        )
        try:
            return self.repository.add(entity)
        except Exception:
            self.storage.delete(stored_filename)
            raise

    def list(self) -> list[Floorplan]:
        return self.repository.list()

    def get(self, floorplan_id: UUID) -> Floorplan:
        floorplan = self.repository.get(floorplan_id)
        if floorplan is None:
            raise NotFoundError("Plano no encontrado.")
        return floorplan

    def delete(self, floorplan_id: UUID) -> None:
        floorplan = self.get(floorplan_id)
        self.repository.delete(floorplan_id)
        self.storage.delete(floorplan.stored_filename)
