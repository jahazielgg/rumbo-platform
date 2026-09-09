from collections.abc import Callable
from uuid import UUID

from app.shared_kernel.errors import ValidationError

from .types import PositioningConfigInput
from ..domain.entities import PositioningConfig, QRAnchor
from ..domain.repositories import PositioningConfigRepository


class PositioningService:
    def __init__(self, repository: PositioningConfigRepository, node_exists: Callable[[UUID, UUID], bool]):
        self.repository = repository
        self.node_exists = node_exists

    def get(self, floorplan_id: UUID) -> PositioningConfig:
        return self.repository.get(floorplan_id) or PositioningConfig(floorplan_id=floorplan_id)

    def save(self, floorplan_id: UUID, data: PositioningConfigInput) -> PositioningConfig:
        anchors = [
            QRAnchor(id=item.id, code=item.code, label=item.label, node_id=item.node_id)
            for item in data.qr_anchors
        ]
        for anchor in anchors:
            if not self.node_exists(floorplan_id, anchor.node_id):
                raise ValidationError(f"El QR '{anchor.label}' debe estar asociado a un nodo existente.")
        return self.repository.save(PositioningConfig(floorplan_id=floorplan_id, qr_anchors=anchors))
