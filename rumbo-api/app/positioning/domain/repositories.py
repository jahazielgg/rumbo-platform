from abc import ABC, abstractmethod
from uuid import UUID

from .entities import PositioningConfig


class PositioningConfigRepository(ABC):
    @abstractmethod
    def get(self, floorplan_id: UUID) -> PositioningConfig | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, config: PositioningConfig) -> PositioningConfig:
        raise NotImplementedError
