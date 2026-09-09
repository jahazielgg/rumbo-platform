from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class SpatialModelRecord(Base):
    __tablename__ = "spatial_models"

    floorplan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("floorplans.id", ondelete="CASCADE"), primary_key=True
    )
    pixels_per_meter: Mapped[float | None] = mapped_column(Float, nullable=True)
    walls: Mapped[list] = mapped_column(JSON, default=list)
    nodes: Mapped[list] = mapped_column(JSON, default=list)
    pois: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class StructuralMapRecord(Base):
    __tablename__ = "structural_maps"

    floorplan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("floorplans.id", ondelete="CASCADE"), primary_key=True
    )
    parser: Mapped[str] = mapped_column(String(120))
    parser_version: Mapped[str] = mapped_column(String(40))
    image_width: Mapped[int] = mapped_column(Integer)
    image_height: Mapped[int] = mapped_column(Integer)
    wall_polygons: Mapped[list] = mapped_column(JSON, default=list)
    obstacle_polygons: Mapped[list] = mapped_column(JSON, default=list)
    doors: Mapped[list] = mapped_column(JSON, default=list)
    window_polygons: Mapped[list] = mapped_column(JSON, default=list)
    spaces: Mapped[list] = mapped_column(JSON, default=list)
    walkable_areas: Mapped[list] = mapped_column(JSON, default=list)
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    estimated_pixels_per_meter: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
