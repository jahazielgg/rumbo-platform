from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class PositioningConfigRecord(Base):
    __tablename__ = "positioning_configs"

    floorplan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("floorplans.id", ondelete="CASCADE"), primary_key=True
    )
    qr_anchors: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
