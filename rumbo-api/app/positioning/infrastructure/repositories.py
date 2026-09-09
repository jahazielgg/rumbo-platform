from uuid import UUID

from sqlalchemy.orm import Session

from ..domain.entities import PositioningConfig, QRAnchor
from ..domain.repositories import PositioningConfigRepository
from .models import PositioningConfigRecord


class SqlAlchemyPositioningConfigRepository(PositioningConfigRepository):
    def __init__(self, db: Session):
        self.db = db

    def get(self, floorplan_id: UUID) -> PositioningConfig | None:
        record = self.db.get(PositioningConfigRecord, str(floorplan_id))
        if record is None:
            return None
        return PositioningConfig(
            floorplan_id=floorplan_id,
            qr_anchors=[
                QRAnchor(
                    id=UUID(item["id"]),
                    code=item["code"],
                    label=item["label"],
                    node_id=UUID(item["node_id"]),
                )
                for item in (record.qr_anchors or [])
            ],
        )

    def save(self, config: PositioningConfig) -> PositioningConfig:
        payload = [
            {
                "id": str(anchor.id),
                "code": anchor.code,
                "label": anchor.label,
                "node_id": str(anchor.node_id),
            }
            for anchor in config.qr_anchors
        ]
        record = self.db.get(PositioningConfigRecord, str(config.floorplan_id))
        if record is None:
            record = PositioningConfigRecord(floorplan_id=str(config.floorplan_id), qr_anchors=payload)
            self.db.add(record)
        else:
            record.qr_anchors = payload
        self.db.commit()
        return config
