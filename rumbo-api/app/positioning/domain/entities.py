from dataclasses import dataclass, field
from uuid import UUID

from app.shared_kernel.errors import ValidationError


@dataclass(frozen=True, slots=True)
class QRAnchor:
    id: UUID
    code: str
    label: str
    node_id: UUID

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValidationError("El QR debe tener un código.")
        if not self.label.strip():
            raise ValidationError("El QR debe tener una etiqueta.")


@dataclass(slots=True)
class PositioningConfig:
    floorplan_id: UUID
    qr_anchors: list[QRAnchor] = field(default_factory=list)

    def __post_init__(self) -> None:
        codes = [anchor.code.strip().lower() for anchor in self.qr_anchors]
        if len(set(codes)) != len(codes):
            raise ValidationError("Los códigos QR deben ser únicos dentro del piso.")
