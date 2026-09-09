from uuid import uuid4

import pytest

from app.navigation.domain.entities import NavigationConfig, NavigationEdge, VerticalConnector
from app.shared_kernel.errors import ValidationError


def test_edge_rejects_self_connection():
    node_id = uuid4()
    with pytest.raises(ValidationError):
        NavigationEdge(id=uuid4(), from_node_id=node_id, to_node_id=node_id)


def test_navigation_rejects_duplicate_undirected_edges():
    a, b = uuid4(), uuid4()
    with pytest.raises(ValidationError):
        NavigationConfig(
            floorplan_id=uuid4(),
            edges=[
                NavigationEdge(id=uuid4(), from_node_id=a, to_node_id=b),
                NavigationEdge(id=uuid4(), from_node_id=b, to_node_id=a),
            ],
        )


def test_vertical_connector_accepts_supported_types():
    connector = VerticalConnector(
        id=uuid4(),
        kind="elevator",
        label="Ascensor principal",
        source_node_id=uuid4(),
        target_floorplan_id=uuid4(),
        target_node_id=uuid4(),
    )
    assert connector.bidirectional is True
