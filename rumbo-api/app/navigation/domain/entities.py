from dataclasses import dataclass, field
from uuid import UUID

from app.shared_kernel.errors import ValidationError


EDGE_KINDS = {"corridor", "doorway"}
CONNECTOR_KINDS = {"elevator", "stairs", "ramp"}


@dataclass(frozen=True, slots=True)
class NavigationEdge:
    id: UUID
    from_node_id: UUID
    to_node_id: UUID
    kind: str = "corridor"
    accessible: bool = True

    def __post_init__(self) -> None:
        if self.from_node_id == self.to_node_id:
            raise ValidationError("Una conexión debe unir dos nodos distintos.")
        if self.kind not in EDGE_KINDS:
            raise ValidationError("Tipo de conexión no soportado.")


@dataclass(frozen=True, slots=True)
class VerticalConnector:
    id: UUID
    kind: str
    label: str
    source_node_id: UUID
    target_floorplan_id: UUID
    target_node_id: UUID
    accessible: bool = True
    bidirectional: bool = True

    def __post_init__(self) -> None:
        if self.kind not in CONNECTOR_KINDS:
            raise ValidationError("El conector vertical debe ser ascensor, escalera o rampa.")
        if not self.label.strip():
            raise ValidationError("El conector vertical debe tener una etiqueta.")


@dataclass(slots=True)
class NavigationConfig:
    floorplan_id: UUID
    edges: list[NavigationEdge] = field(default_factory=list)
    vertical_connectors: list[VerticalConnector] = field(default_factory=list)

    def __post_init__(self) -> None:
        seen_pairs: set[frozenset[UUID]] = set()
        for edge in self.edges:
            pair = frozenset((edge.from_node_id, edge.to_node_id))
            if pair in seen_pairs:
                raise ValidationError("No puede haber conexiones duplicadas entre los mismos nodos.")
            seen_pairs.add(pair)
