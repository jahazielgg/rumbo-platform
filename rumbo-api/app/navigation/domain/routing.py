from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import inf
from uuid import UUID

from app.shared_kernel.errors import ValidationError


@dataclass(frozen=True, slots=True)
class RouteNode:
    floorplan_id: UUID
    node_id: UUID
    label: str
    x: float
    y: float

    @property
    def key(self) -> tuple[UUID, UUID]:
        return (self.floorplan_id, self.node_id)


@dataclass(frozen=True, slots=True)
class RouteLink:
    from_key: tuple[UUID, UUID]
    to_key: tuple[UUID, UUID]
    distance_meters: float
    kind: str
    label: str | None = None
    accessible: bool = True


@dataclass(frozen=True, slots=True)
class RoutePath:
    nodes: list[RouteNode]
    links: list[RouteLink]
    total_distance_meters: float


def shortest_path(
    *,
    nodes: dict[tuple[UUID, UUID], RouteNode],
    links: list[RouteLink],
    start: tuple[UUID, UUID],
    destination: tuple[UUID, UUID],
    accessible_only: bool = False,
) -> RoutePath:
    if start not in nodes or destination not in nodes:
        raise ValidationError("El origen o el destino no existe en el mapa de navegación.")

    adjacency: dict[tuple[UUID, UUID], list[RouteLink]] = {key: [] for key in nodes}
    for link in links:
        if accessible_only and not link.accessible:
            continue
        if link.from_key in adjacency and link.to_key in adjacency:
            adjacency[link.from_key].append(link)

    distances = {key: inf for key in nodes}
    distances[start] = 0.0
    previous: dict[tuple[UUID, UUID], tuple[tuple[UUID, UUID], RouteLink]] = {}
    queue: list[tuple[float, str, tuple[UUID, UUID]]] = []
    heappush(queue, (0.0, f"{start[0]}:{start[1]}", start))

    while queue:
        current_distance, _, current = heappop(queue)
        if current_distance > distances[current]:
            continue
        if current == destination:
            break
        for link in adjacency[current]:
            candidate = current_distance + max(link.distance_meters, 0.001)
            if candidate < distances[link.to_key]:
                distances[link.to_key] = candidate
                previous[link.to_key] = (current, link)
                heappush(queue, (candidate, f"{link.to_key[0]}:{link.to_key[1]}", link.to_key))

    if distances[destination] == inf:
        mode = " accesible" if accessible_only else ""
        raise ValidationError(f"No existe una ruta{mode} entre el origen y el destino.")

    keys: list[tuple[UUID, UUID]] = [destination]
    path_links: list[RouteLink] = []
    cursor = destination
    while cursor != start:
        previous_node, link = previous[cursor]
        path_links.append(link)
        cursor = previous_node
        keys.append(cursor)

    keys.reverse()
    path_links.reverse()
    return RoutePath(
        nodes=[nodes[key] for key in keys],
        links=path_links,
        total_distance_meters=distances[destination],
    )
