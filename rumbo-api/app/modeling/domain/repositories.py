from abc import ABC, abstractmethod
from uuid import UUID

from .entities import SpatialModel


class SpatialModelRepository(ABC):
    @abstractmethod
    def get(self, floorplan_id: UUID) -> SpatialModel | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, model: SpatialModel) -> SpatialModel:
        raise NotImplementedError
