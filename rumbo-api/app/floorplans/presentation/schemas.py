from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FloorplanResponse(BaseModel):
    id: UUID
    name: str
    building_name: str
    floor_label: str
    original_filename: str
    media_type: str
    created_at: datetime
    file_url: str
    preview_url: str
