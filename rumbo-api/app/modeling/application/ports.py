from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from ..domain.structural import StructuralAnalysis


class StructuralParser(ABC):
    @abstractmethod
    def analyze(
        self,
        *,
        floorplan_id: UUID,
        content: bytes,
        media_type: str,
        pixels_per_meter: float | None = None,
        raster_scale: float = 2.0,
    ) -> StructuralAnalysis:
        raise NotImplementedError
