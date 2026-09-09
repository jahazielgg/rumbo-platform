from __future__ import annotations

from collections.abc import Callable
from math import hypot
from uuid import UUID

from app.shared_kernel.errors import ValidationError
from app.shared_kernel.geometry import segments_properly_cross

from .types import RouteFloorSource, RouteRequest, RouteWallSource
from ..domain.routing import RouteLink, RouteNode, RoutePath, shortest_path


VERTICAL_COST_METERS = {
    "elevator": 6.0,
    "stairs": 10.0,
    "ramp": 12.0,
}


def _properly_crosses_wall(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    wall: RouteWallSource,
) -> bool:
    """Return True only for a real through-wall crossing (see shared_kernel.geometry)."""
    return segments_properly_cross(ax, ay, bx, by, wall.start_x, wall.start_y, wall.end_x, wall.end_y)


def _edge_crosses_any_wall(ax: float, ay: float, bx: float, by: float, walls: list[RouteWallSource]) -> bool:
    return any(_properly_crosses_wall(ax, ay, bx, by, wall) for wall in walls)


class RoutePlanningService:
    def __init__(self, load_network: Callable[[UUID], list[RouteFloorSource]]):
        self.load_network = load_network

    def plan(self, request: RouteRequest) -> RoutePath:
        floors = self.load_network(request.start_floorplan_id)
        if not floors:
            raise ValidationError("No hay un mapa de navegación disponible para ese edificio.")
        floor_ids = {floor.floorplan_id for floor in floors}
        if request.destination_floorplan_id not in floor_ids:
            raise ValidationError("El destino debe pertenecer al mismo edificio que el origen.")

        nodes: dict[tuple[UUID, UUID], RouteNode] = {}
        links: list[RouteLink] = []

        for floor in floors:
            node_lookup = {node.id: node for node in floor.nodes}
            for node in floor.nodes:
                route_node = RouteNode(
                    floorplan_id=floor.floorplan_id,
                    node_id=node.id,
                    label=node.label,
                    x=node.x,
                    y=node.y,
                )
                nodes[route_node.key] = route_node

            for edge in floor.edges:
                a = node_lookup.get(edge.from_node_id)
                b = node_lookup.get(edge.to_node_id)
                if not a or not b:
                    continue
                if _edge_crosses_any_wall(a.x, a.y, b.x, b.y, floor.walls):
                    # Never route through a modeled physical barrier, even if a stale or
                    # manually-created navigation edge still exists in persisted data.
                    continue
                px = hypot(b.x - a.x, b.y - a.y)
                distance_meters = px / floor.pixels_per_meter if floor.pixels_per_meter else px
                forward = RouteLink(
                    from_key=(floor.floorplan_id, edge.from_node_id),
                    to_key=(floor.floorplan_id, edge.to_node_id),
                    distance_meters=distance_meters,
                    kind="corridor",
                    accessible=edge.accessible,
                )
                reverse = RouteLink(
                    from_key=forward.to_key,
                    to_key=forward.from_key,
                    distance_meters=distance_meters,
                    kind="corridor",
                    accessible=edge.accessible,
                )
                links.extend((forward, reverse))

            for connector in floor.connectors:
                cost = VERTICAL_COST_METERS.get(connector.kind, 10.0)
                source_key = (floor.floorplan_id, connector.source_node_id)
                target_key = (connector.target_floorplan_id, connector.target_node_id)
                links.append(
                    RouteLink(
                        from_key=source_key,
                        to_key=target_key,
                        distance_meters=cost,
                        kind=connector.kind,
                        label=connector.label,
                        accessible=connector.accessible,
                    )
                )
                if connector.bidirectional:
                    links.append(
                        RouteLink(
                            from_key=target_key,
                            to_key=source_key,
                            distance_meters=cost,
                            kind=connector.kind,
                            label=connector.label,
                            accessible=connector.accessible,
                        )
                    )

        return shortest_path(
            nodes=nodes,
            links=links,
            start=(request.start_floorplan_id, request.start_node_id),
            destination=(request.destination_floorplan_id, request.destination_node_id),
            accessible_only=request.accessible_only,
        )
