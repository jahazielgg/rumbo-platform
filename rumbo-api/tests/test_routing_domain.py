from uuid import UUID

import pytest

from app.navigation.domain.routing import RouteLink, RouteNode, shortest_path
from app.shared_kernel.errors import ValidationError


FLOOR = UUID("10000000-0000-4000-8000-000000000001")
A = UUID("20000000-0000-4000-8000-000000000001")
B = UUID("20000000-0000-4000-8000-000000000002")
C = UUID("20000000-0000-4000-8000-000000000003")


def test_shortest_path_prefers_lower_distance():
    nodes = {
        (FLOOR, A): RouteNode(FLOOR, A, "A", 0, 0),
        (FLOOR, B): RouteNode(FLOOR, B, "B", 1, 0),
        (FLOOR, C): RouteNode(FLOOR, C, "C", 2, 0),
    }
    links = [
        RouteLink((FLOOR, A), (FLOOR, B), 2, "corridor"),
        RouteLink((FLOOR, B), (FLOOR, C), 2, "corridor"),
        RouteLink((FLOOR, A), (FLOOR, C), 10, "corridor"),
    ]
    route = shortest_path(nodes=nodes, links=links, start=(FLOOR, A), destination=(FLOOR, C))
    assert [node.node_id for node in route.nodes] == [A, B, C]
    assert route.total_distance_meters == 4


def test_accessible_route_excludes_inaccessible_links():
    nodes = {
        (FLOOR, A): RouteNode(FLOOR, A, "A", 0, 0),
        (FLOOR, B): RouteNode(FLOOR, B, "B", 1, 0),
        (FLOOR, C): RouteNode(FLOOR, C, "C", 2, 0),
    }
    links = [
        RouteLink((FLOOR, A), (FLOOR, C), 1, "stairs", accessible=False),
        RouteLink((FLOOR, A), (FLOOR, B), 3, "corridor", accessible=True),
        RouteLink((FLOOR, B), (FLOOR, C), 3, "corridor", accessible=True),
    ]
    route = shortest_path(
        nodes=nodes,
        links=links,
        start=(FLOOR, A),
        destination=(FLOOR, C),
        accessible_only=True,
    )
    assert [node.node_id for node in route.nodes] == [A, B, C]
    assert route.total_distance_meters == 6


def test_route_fails_when_graph_is_disconnected():
    nodes = {
        (FLOOR, A): RouteNode(FLOOR, A, "A", 0, 0),
        (FLOOR, C): RouteNode(FLOOR, C, "C", 2, 0),
    }
    with pytest.raises(ValidationError, match="No existe una ruta"):
        shortest_path(nodes=nodes, links=[], start=(FLOOR, A), destination=(FLOOR, C))
