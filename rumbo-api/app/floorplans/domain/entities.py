from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Floorplan:
    id: UUID
    name: str
    building_name: str
    floor_label: str
    original_filename: str
    stored_filename: str
    media_type: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        name: str,
        building_name: str,
        floor_label: str,
        original_filename: str,
        stored_filename: str,
        media_type: str,
    ) -> "Floorplan":
        return cls(
            id=uuid4(),
            name=name.strip(),
            building_name=building_name.strip(),
            floor_label=floor_label.strip(),
            original_filename=original_filename,
            stored_filename=stored_filename,
            media_type=media_type,
            created_at=datetime.now(timezone.utc),
        )
