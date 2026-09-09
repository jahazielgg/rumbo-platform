from collections.abc import Callable
from uuid import UUID

from app.shared_kernel.errors import ValidationError

from .types import NavigationConfigInput
from ..domain.entities import NavigationConfig, NavigationEdge, VerticalConnector
from ..domain.repositories import NavigationConfigRepository


class NavigationService:
    def __init__(
        self,
        repository: NavigationConfigRepository,
        node_exists: Callable[[UUID, UUID], bool],
        floorplan_exists: Callable[[UUID], bool],
    ):
        self.repository = repository
        self.node_exists = node_exists
        self.floorplan_exists = floorplan_exists

    def get(self, floorplan_id: UUID) -> NavigationConfig:
        return self.repository.get(floorplan_id) or NavigationConfig(floorplan_id=floorplan_id)

    def save(self, floorplan_id: UUID, data: NavigationConfigInput) -> NavigationConfig:
        edges = [
            NavigationEdge(
                id=item.id,
                from_node_id=item.from_node_id,
                to_node_id=item.to_node_id,
                kind=item.kind,
                accessible=item.accessible,
            )
            for item in data.edges
        ]
        connectors = [
            VerticalConnector(
                id=item.id,
                kind=item.kind,
                label=item.label,
                source_node_id=item.source_node_id,
                target_floorplan_id=item.target_floorplan_id,
                target_node_id=item.target_node_id,
                accessible=item.accessible,
                bidirectional=item.bidirectional,
            )
            for item in data.vertical_connectors
        ]

        for edge in edges:
            if not self.node_exists(floorplan_id, edge.from_node_id) or not self.node_exists(floorplan_id, edge.to_node_id):
                raise ValidationError("Las conexiones deben apuntar a nodos existentes en el piso actual.")

        for connector in connectors:
            if not self.node_exists(floorplan_id, connector.source_node_id):
                raise ValidationError("El nodo de origen del conector vertical no existe.")
            if connector.target_floorplan_id == floorplan_id:
                raise ValidationError("Un conector entre pisos debe apuntar a un piso distinto.")
            if not self.floorplan_exists(connector.target_floorplan_id):
                raise ValidationError("El piso de destino del conector vertical no existe.")
            if not self.node_exists(connector.target_floorplan_id, connector.target_node_id):
                raise ValidationError("El nodo de destino del conector vertical no existe.")

        return self.repository.save(
            NavigationConfig(floorplan_id=floorplan_id, edges=edges, vertical_connectors=connectors)
        )
