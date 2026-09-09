from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.entities import Floorplan
from ..domain.repositories import FloorplanRepository
from .models import FloorplanModel


def _to_entity(model: FloorplanModel) -> Floorplan:
    return Floorplan(
        id=UUID(model.id),
        name=model.name,
        building_name=model.building_name,
        floor_label=model.floor_label,
        original_filename=model.original_filename,
        stored_filename=model.stored_filename,
        media_type=model.media_type,
        created_at=model.created_at,
    )


class SqlAlchemyFloorplanRepository(FloorplanRepository):
    def __init__(self, db: Session):
        self.db = db

    def add(self, floorplan: Floorplan) -> Floorplan:
        model = FloorplanModel(
            id=str(floorplan.id),
            name=floorplan.name,
            building_name=floorplan.building_name,
            floor_label=floorplan.floor_label,
            original_filename=floorplan.original_filename,
            stored_filename=floorplan.stored_filename,
            media_type=floorplan.media_type,
            created_at=floorplan.created_at,
        )
        self.db.add(model)
        self.db.commit()
        return floorplan

    def list(self) -> list[Floorplan]:
        models = self.db.scalars(select(FloorplanModel).order_by(FloorplanModel.created_at.desc())).all()
        return [_to_entity(model) for model in models]

    def get(self, floorplan_id: UUID) -> Floorplan | None:
        model = self.db.get(FloorplanModel, str(floorplan_id))
        return _to_entity(model) if model else None

    def delete(self, floorplan_id: UUID) -> bool:
        model = self.db.get(FloorplanModel, str(floorplan_id))
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
