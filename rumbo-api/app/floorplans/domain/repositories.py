from abc import ABC, abstractmethod
from uuid import UUID

from .entities import Floorplan


class FloorplanRepository(ABC):
    @abstractmethod
    def add(self, floorplan: Floorplan) -> Floorplan:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[Floorplan]:
        raise NotImplementedError

    @abstractmethod
    def get(self, floorplan_id: UUID) -> Floorplan | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, floorplan_id: UUID) -> bool:
        raise NotImplementedError
