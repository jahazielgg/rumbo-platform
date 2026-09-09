from pathlib import Path
from uuid import uuid4

from ..application.ports import FloorplanStorage


class LocalFloorplanStorage(FloorplanStorage):
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, *, content: bytes, suffix: str) -> str:
        filename = f"{uuid4()}{suffix}"
        (self.root / filename).write_bytes(content)
        return filename

    def delete(self, stored_filename: str) -> None:
        path = self.root / stored_filename
        if path.exists():
            path.unlink()

    def resolve(self, stored_filename: str) -> Path:
        return self.root / stored_filename
