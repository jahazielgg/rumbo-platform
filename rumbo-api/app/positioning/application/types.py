from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class QRAnchorInput:
    id: UUID
    code: str
    label: str
    node_id: UUID


@dataclass(frozen=True, slots=True)
class PositioningConfigInput:
    qr_anchors: list[QRAnchorInput]
