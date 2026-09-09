from abc import ABC, abstractmethod
from uuid import UUID

from .entities import NavigationConfig


class NavigationConfigRepository(ABC):
    @abstractmethod
    def get(self, floorplan_id: UUID) -> NavigationConfig | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, config: NavigationConfig) -> NavigationConfig:
        raise NotImplementedError
