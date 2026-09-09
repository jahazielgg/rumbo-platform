from uuid import UUID

from sqlalchemy.orm import Session

from ..domain.entities import NavigationConfig, NavigationEdge, VerticalConnector
from ..domain.repositories import NavigationConfigRepository
from .models import NavigationConfigRecord


class SqlAlchemyNavigationConfigRepository(NavigationConfigRepository):
    def __init__(self, db: Session):
        self.db = db

    def get(self, floorplan_id: UUID) -> NavigationConfig | None:
        record = self.db.get(NavigationConfigRecord, str(floorplan_id))
        if record is None:
            return None
        return NavigationConfig(
            floorplan_id=floorplan_id,
            edges=[
                NavigationEdge(
                    id=UUID(item["id"]),
                    from_node_id=UUID(item["from_node_id"]),
                    to_node_id=UUID(item["to_node_id"]),
                    kind=item.get("kind", "corridor"),
                    accessible=item.get("accessible", True),
                )
                for item in (record.edges or [])
            ],
            vertical_connectors=[
                VerticalConnector(
                    id=UUID(item["id"]),
                    kind=item["kind"],
                    label=item["label"],
                    source_node_id=UUID(item["source_node_id"]),
                    target_floorplan_id=UUID(item["target_floorplan_id"]),
                    target_node_id=UUID(item["target_node_id"]),
                    accessible=item.get("accessible", True),
                    bidirectional=item.get("bidirectional", True),
                )
                for item in (record.vertical_connectors or [])
            ],
        )

    def save(self, config: NavigationConfig) -> NavigationConfig:
        edges = [
            {
                "id": str(edge.id),
                "from_node_id": str(edge.from_node_id),
                "to_node_id": str(edge.to_node_id),
                "kind": edge.kind,
                "accessible": edge.accessible,
            }
            for edge in config.edges
        ]
        connectors = [
            {
                "id": str(connector.id),
                "kind": connector.kind,
                "label": connector.label,
                "source_node_id": str(connector.source_node_id),
                "target_floorplan_id": str(connector.target_floorplan_id),
                "target_node_id": str(connector.target_node_id),
                "accessible": connector.accessible,
                "bidirectional": connector.bidirectional,
            }
            for connector in config.vertical_connectors
        ]
        record = self.db.get(NavigationConfigRecord, str(config.floorplan_id))
        if record is None:
            record = NavigationConfigRecord(
                floorplan_id=str(config.floorplan_id),
                edges=edges,
                vertical_connectors=connectors,
            )
            self.db.add(record)
        else:
            record.edges = edges
            record.vertical_connectors = connectors
        self.db.commit()
        return config
