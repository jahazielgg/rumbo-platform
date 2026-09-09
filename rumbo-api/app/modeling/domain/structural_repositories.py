from abc import ABC, abstractmethod

from .structural import StructuralMap


class StructuralMapRepository(ABC):
    @abstractmethod
    def save(self, structural_map: StructuralMap) -> StructuralMap:
        raise NotImplementedError
