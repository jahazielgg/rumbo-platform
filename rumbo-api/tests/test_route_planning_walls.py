from uuid import UUID

from app.navigation.application.routing import RoutePlanningService
from app.navigation.application.types import (
    RouteEdgeSource,
    RouteFloorSource,
    RouteNodeSource,
    RouteRequest,
    RouteWallSource,
)


FLOOR = UUID("10000000-0000-4000-8000-000000000001")
A = UUID("20000000-0000-4000-8000-000000000001")
B = UUID("20000000-0000-4000-8000-000000000002")
C = UUID("20000000-0000-4000-8000-000000000003")
D = UUID("20000000-0000-4000-8000-000000000004")


def test_route_planner_ignores_edge_that_crosses_a_wall():
    floor = RouteFloorSource(
        floorplan_id=FLOOR,
        building_name="Test",
        floor_label="Piso 1",
        pixels_per_meter=1,
        nodes=[
            RouteNodeSource(A, "A", 0, 0),
            RouteNodeSource(B, "B", 10, 0),
            RouteNodeSource(C, "C", 0, 3),
            RouteNodeSource(D, "D", 10, 3),
        ],
        edges=[
            RouteEdgeSource(A, B, True),  # shortest, but crosses the wall
            RouteEdgeSource(A, C, True),
            RouteEdgeSource(C, D, True),
            RouteEdgeSource(D, B, True),
        ],
        walls=[RouteWallSource(5, -1, 5, 1)],
        connectors=[],
    )
    planner = RoutePlanningService(lambda _: [floor])

    route = planner.plan(RouteRequest(FLOOR, A, FLOOR, B))

    assert [node.node_id for node in route.nodes] == [A, C, D, B]
    assert route.total_distance_meters == 16


def test_route_planner_allows_endpoint_touch_and_collinear_segments():
    floor = RouteFloorSource(
        floorplan_id=FLOOR,
        building_name="Test",
        floor_label="Piso 1",
        pixels_per_meter=1,
        nodes=[
            RouteNodeSource(A, "A", 0, 0),
            RouteNodeSource(B, "B", 10, 0),
        ],
        edges=[RouteEdgeSource(A, B, True)],
        walls=[
            RouteWallSource(10, 0, 10, 5),  # touches at B
            RouteWallSource(2, 0, 8, 0),    # collinear with the route
        ],
        connectors=[],
    )
    planner = RoutePlanningService(lambda _: [floor])

    route = planner.plan(RouteRequest(FLOOR, A, FLOOR, B))

    assert [node.node_id for node in route.nodes] == [A, B]
