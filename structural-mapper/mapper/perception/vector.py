"""Perception backend fed by exact vector geometry (PDF/SVG strokes)."""
from __future__ import annotations

import numpy as np

from ..contracts import RasterInput, Scale, StructuralMasks


class VectorPerceiver:
    name = "vector-strokes"

    def perceive(self, source: RasterInput, scale: Scale | None) -> StructuralMasks:
        if source.vector_walls is None:
            raise ValueError("source has no vector walls")
        walls = source.vector_walls.astype(bool)
        empty = np.zeros_like(walls, dtype=bool)
        return StructuralMasks(wall=walls, door=empty, window=empty.copy(), wall_probability=walls.astype(np.float32), backend=self.name)
