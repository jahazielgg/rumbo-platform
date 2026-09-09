from __future__ import annotations

from typing import Protocol

from ..contracts import RasterInput, Scale, StructuralMasks


class Perceiver(Protocol):
    name: str

    def perceive(self, source: RasterInput, scale: Scale | None) -> StructuralMasks: ...
