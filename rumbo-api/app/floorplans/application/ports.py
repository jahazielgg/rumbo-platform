from abc import ABC, abstractmethod
from pathlib import Path


class FloorplanStorage(ABC):
    @abstractmethod
    def save(self, *, content: bytes, suffix: str) -> str:
        """Return the stored filename, not an absolute filesystem path."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, stored_filename: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def resolve(self, stored_filename: str) -> Path:
        raise NotImplementedError
