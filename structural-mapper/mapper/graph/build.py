"""Semantic navigation graph.

Nodes exist only where they are useful for wayfinding:

* `decision`  – corridor junctions (skeleton degree >= 3)
* `waypoint`  – bends where a straight segment would cross a wall or turn sharply
* `door`      – every kept opening between spaces
* `entrance`  – openings to the outside
* `room`      – one anchor per reachable room (destination for POIs)
* `connector` – elevator / stairs / ramp spaces (cross-floor links are configured later)

Every edge is checked against the wall polygons; an edge that would cross a wall is
refined along the skeleton path or dropped. Topological correctness beats looks.
"""
from __future__ import annotations

from itertools import count

import networkx as nx
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

from ..contracts import GraphEdge, GraphNode, NavigationGraph, Opening, Scale, Space, WallElement
from ..geometry import rasterize
from .skeleton import collapse_degree_two, merge_close_nodes, prune_spurs, rdp, skeleton_graph

TURN_TOLERANCE_M = 0.35
MERGE_M = 0.7
SPUR_M = 1.2
COLLINEAR_COS = -0.94  # ~160 degrees


class GraphBuilder:
    def __init__(self, scale: Scale, shape: tuple[int, int], walls: list[WallElement]):
        self.scale = scale
        self.shape = shape
        barrier = unary_union([w.polygon for w in walls]) if walls else Polygon()
        # shrink slightly so touching a wall face is not a crossing
        self.barrier = barrier.buffer(-0.25) if not barrier.is_empty else barrier
        self.prepared = prep(self.barrier)
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[frozenset, GraphEdge] = {}
        self.ids = count(1)
        self.skeleton: nx.Graph | None = None
        self.skeleton_node_ids: dict[int, str] = {}
        self.dropped_crossing = 0
        self.room_ids: set[str] = set()

    # ---- public --------------------------------------------------------------------
    def build(self, spaces: list[Space], openings: list[Opening], walkable: dict[str, Polygon]) -> NavigationGraph:
        by_space = {s.id: s for s in spaces}
        self.room_ids = {s.id for s in spaces if s.kind in ("room", "vertical")}
        circulation = [walkable[s.id] for s in spaces if s.kind == "circulation" and s.id in walkable]
        if circulation:
            mask = rasterize(circulation, self.shape)
            self._build_skeleton(mask, openings)
        for opening in openings:
            self._attach_opening(opening, by_space, walkable)
        self._connect_room_nodes(walkable)
        self._simplify()
        self.dropped_crossing = self._drop_crossing_edges()
        return NavigationGraph(nodes=list(self.nodes.values()), edges=list(self.edges.values()))

    def _drop_crossing_edges(self) -> int:
        """Safety net: the invariant is enforced at construction, but never trust it blindly."""
        dropped = 0
        for key in list(self.edges):
            a, b = tuple(key)
            na, nb = self.nodes[a], self.nodes[b]
            if not self._visible((na.x, na.y), (nb.x, nb.y)):
                del self.edges[key]
                dropped += 1
        if dropped:
            connected = {n for key in self.edges for n in key}
            for node_id in [n.id for n in self.nodes.values() if n.id not in connected and n.kind in ("waypoint", "decision")]:
                del self.nodes[node_id]
        return dropped

    # ---- skeleton of circulation --------------------------------------------------------
    def _build_skeleton(self, mask: np.ndarray, openings: list[Opening]) -> None:
        graph = skeleton_graph(mask)
        if graph.number_of_nodes() == 0:
            return
        protected: set[int] = set()
        for opening in openings:
            nearest = self._nearest_skeleton_node(graph, opening.center, self.scale.px(1.0))
            if nearest is not None:
                protected.add(nearest)
        import cv2

        distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)

        def local_width(x: float, y: float) -> float:
            xi, yi = int(round(x)), int(round(y))
            if 0 <= yi < distance.shape[0] and 0 <= xi < distance.shape[1]:
                return float(distance[yi, xi])
            return 0.0

        prune_spurs(graph, self.scale.px(SPUR_M), protected, local_width)
        merge_close_nodes(graph, self.scale.px(MERGE_M), protected)
        collapse_degree_two(graph, protected)
        self.skeleton = graph
        for node, data in graph.nodes(data=True):
            kind = "decision" if graph.degree(node) >= 3 else "waypoint"
            self.skeleton_node_ids[node] = self._add_node(data["x"], data["y"], kind)
        for a, b, data in graph.edges(data=True):
            path = data["path"]
            path = path if self._near(path[0], graph.nodes[a]) else path[::-1]
            self._add_polyline(self.skeleton_node_ids[a], self.skeleton_node_ids[b], [(graph.nodes[a]["x"], graph.nodes[a]["y"])] + list(path) + [(graph.nodes[b]["x"], graph.nodes[b]["y"])], "corridor")

    @staticmethod
    def _near(pixel, attrs) -> bool:
        return abs(pixel[0] - attrs["x"]) <= 2 and abs(pixel[1] - attrs["y"]) <= 2

    def _nearest_skeleton_node(self, graph: nx.Graph, point, radius: float) -> int | None:
        best, best_d = None, radius
        for node, data in graph.nodes(data=True):
            d = np.hypot(data["x"] - point[0], data["y"] - point[1])
            if d < best_d:
                best, best_d = node, d
        return best

    # ---- openings --------------------------------------------------------------------------
    def _attach_opening(self, opening: Opening, spaces: dict[str, Space], walkable: dict[str, Polygon]) -> None:
        kind = "entrance" if opening.kind == "entrance" else "door"
        door_id = self._add_node(opening.center[0], opening.center[1], kind, opening_id=opening.id)
        depth = max(2.0, opening.polygon.area / max(opening.width_px, 1.0))
        for sign, space_id in zip((1, -1), opening.space_ids):
            if space_id is None or space_id not in spaces:
                continue
            space = spaces[space_id]
            inside = (
                opening.center[0] + sign * opening.normal[0] * (depth / 2 + self.scale.px(0.4)),
                opening.center[1] + sign * opening.normal[1] * (depth / 2 + self.scale.px(0.4)),
            )
            if not space.polygon.buffer(1.0).contains(Point(inside)):
                other = (
                    opening.center[0] - sign * opening.normal[0] * (depth / 2 + self.scale.px(0.4)),
                    opening.center[1] - sign * opening.normal[1] * (depth / 2 + self.scale.px(0.4)),
                )
                if space.polygon.buffer(1.0).contains(Point(other)):
                    inside = other
            if space.kind == "circulation":
                self._connect_to_skeleton(door_id, inside, space)
            elif space.kind in ("room", "vertical"):
                self._connect_to_room(door_id, inside, space, walkable.get(space.id, space.polygon))

    def _connect_to_skeleton(self, door_id: str, inside, space: Space) -> None:
        graph = self.skeleton
        door = self.nodes[door_id]
        if graph is None or graph.number_of_nodes() == 0:
            # circulation without skeleton (tiny space): treat like a room
            self._connect_to_room(door_id, inside, space, space.polygon)
            return
        # candidate attachment points: existing nodes first, then points along edges
        candidates: list[tuple[float, str | None, tuple[float, float], tuple | None]] = []
        for node, data in graph.nodes(data=True):
            p = (data["x"], data["y"])
            candidates.append((np.hypot(p[0] - inside[0], p[1] - inside[1]), self.skeleton_node_ids[node], p, None))
        for a, b, data in graph.edges(data=True):
            path = data["path"]
            step = max(1, len(path) // 40)
            for index in range(0, len(path), step):
                p = path[index]
                candidates.append((np.hypot(p[0] - inside[0], p[1] - inside[1]), None, (float(p[0]), float(p[1])), (a, b, index)))
        candidates.sort(key=lambda item: item[0])
        merge = self.scale.px(MERGE_M)
        for distance, node_id, point, edge_ref in candidates[:400]:
            if not self._visible((door.x, door.y), point):
                continue
            if node_id is None and edge_ref is not None:
                node_id = self._split_skeleton_edge(edge_ref, point, merge)
            if node_id is None:
                continue
            self._add_edge(door_id, node_id, "doorway")
            return
        # nothing visible: fall back to a waypoint just inside the door, connected to nearest visible skeleton point via straight line attempts
        way_id = self._add_node(inside[0], inside[1], "waypoint", space_id=space.id)
        self._add_edge(door_id, way_id, "doorway")
        for distance, node_id, point, edge_ref in candidates[:400]:
            if not self._visible(inside, point):
                continue
            if node_id is None and edge_ref is not None:
                node_id = self._split_skeleton_edge(edge_ref, point, merge)
            if node_id is None:
                continue
            self._add_edge(way_id, node_id, "corridor")
            return

    def _split_skeleton_edge(self, edge_ref, point, merge: float) -> str | None:
        a, b, index = edge_ref
        graph = self.skeleton
        if graph is None or not graph.has_edge(a, b):
            return None
        data = graph[a][b]
        path = data["path"]
        for end in (a, b):
            attrs = graph.nodes[end]
            if np.hypot(attrs["x"] - point[0], attrs["y"] - point[1]) < merge:
                return self.skeleton_node_ids[end]
        new = max(graph.nodes) + 1
        graph.add_node(new, x=float(point[0]), y=float(point[1]))
        first, second = path[: index + 1], path[index:]
        graph.remove_edge(a, b)
        graph.add_edge(a, new, path=first, length=_length(first))
        graph.add_edge(new, b, path=second, length=_length(second))
        node_id = self._add_node(point[0], point[1], "waypoint")
        self.skeleton_node_ids[new] = node_id
        # replace the straight polyline edges in the semantic graph
        self._remove_edge(self.skeleton_node_ids[a], self.skeleton_node_ids[b])
        self._add_polyline(self.skeleton_node_ids[a], node_id, [(graph.nodes[a]["x"], graph.nodes[a]["y"])] + list(first) + [point], "corridor")
        self._add_polyline(node_id, self.skeleton_node_ids[b], [point] + list(second) + [(graph.nodes[b]["x"], graph.nodes[b]["y"])], "corridor")
        return node_id

    def _connect_to_room(self, door_id: str, inside, space: Space, walk: Polygon) -> None:
        door = self.nodes[door_id]
        anchor = self._room_anchor(space, walk)
        existing = [n for n in self.nodes.values() if n.kind in ("room", "connector") and n.space_id == space.id]
        target = existing[0] if existing else None
        if target is None:
            kind = "connector" if space.kind == "vertical" else "room"
            target = self.nodes[self._add_node(anchor.x, anchor.y, kind, space_id=space.id, label=space.label, connector_kind=space.connector_kind)]
        if self._visible((door.x, door.y), (target.x, target.y)):
            self._add_edge(door_id, target.id, "doorway")
            return
        way_id = self._add_node(inside[0], inside[1], "waypoint", space_id=space.id)
        self._add_edge(door_id, way_id, "doorway")
        if self._visible(inside, (target.x, target.y)):
            self._add_edge(way_id, target.id, "corridor")
        else:
            self._route_inside(way_id, target.id, walk)

    def _room_anchor(self, space: Space, walk: Polygon) -> Point:
        try:
            from shapely.ops import polylabel

            return polylabel(walk if walk.geom_type == "Polygon" else space.polygon, tolerance=1.0)
        except Exception:
            return space.polygon.representative_point()

    def _route_inside(self, from_id: str, to_id: str, walk: Polygon) -> None:
        """Connect two nodes inside one space through its own skeleton (non-convex rooms)."""
        mask = rasterize([walk], self.shape)
        graph = skeleton_graph(mask)
        if graph.number_of_nodes() == 0:
            return
        a, b = self.nodes[from_id], self.nodes[to_id]
        start = self._nearest_skeleton_node(graph, (a.x, a.y), self.scale.px(3.0))
        end = self._nearest_skeleton_node(graph, (b.x, b.y), self.scale.px(3.0))
        if start is None or end is None:
            return
        try:
            route = nx.shortest_path(graph, start, end, weight="length")
        except nx.NetworkXNoPath:
            return
        points = [(a.x, a.y)]
        for u, v in zip(route, route[1:]):
            path = graph[u][v]["path"]
            path = path if self._near(path[0], graph.nodes[u]) else path[::-1]
            points.extend(path)
        points.append((b.x, b.y))
        self._add_polyline(from_id, to_id, points, "corridor")

    def _connect_room_nodes(self, walkable: dict[str, Polygon]) -> None:
        """Rooms with several doors may have several waypoints; link them when visible.

        Circulation spaces are covered by the skeleton and are deliberately excluded: a
        visibility clique across a large hall is the opposite of a minimal graph.
        """
        by_space: dict[str, list[GraphNode]] = {}
        for node in self.nodes.values():
            if node.space_id and node.kind in ("room", "waypoint", "connector") and node.space_id in self.room_ids:
                by_space.setdefault(node.space_id, []).append(node)
        for nodes in by_space.values():
            for i, a in enumerate(nodes):
                for b in nodes[i + 1 :]:
                    if frozenset((a.id, b.id)) in self.edges:
                        continue
                    if self._visible((a.x, a.y), (b.x, b.y)):
                        self._add_edge(a.id, b.id, "corridor")

    # ---- primitives ------------------------------------------------------------------------
    def _add_node(self, x: float, y: float, kind: str, **attrs) -> str:
        node_id = f"n{next(self.ids)}"
        self.nodes[node_id] = GraphNode(id=node_id, x=float(x), y=float(y), kind=kind, **attrs)  # type: ignore[arg-type]
        return node_id

    def _add_edge(self, a: str, b: str, kind: str) -> None:
        if a == b:
            return
        key = frozenset((a, b))
        if key in self.edges:
            return
        na, nb = self.nodes[a], self.nodes[b]
        self.edges[key] = GraphEdge(from_id=a, to_id=b, kind=kind, length_px=float(np.hypot(na.x - nb.x, na.y - nb.y)))  # type: ignore[arg-type]

    def _remove_edge(self, a: str, b: str) -> None:
        # also drop any bend waypoints created for this polyline
        key = frozenset((a, b))
        if key in self.edges:
            del self.edges[key]
            return
        for node in list(self.nodes.values()):
            if node.kind == "waypoint" and node.label == f"bend:{a}:{b}":
                for k in [k for k in self.edges if node.id in k]:
                    del self.edges[k]
                del self.nodes[node.id]

    def _add_polyline(self, a: str, b: str, points, kind: str) -> None:
        """Add a wall-safe chain between two nodes: RDP simplified, refined where needed."""
        simplified = self._wall_safe(points)
        previous = a
        for bend in simplified[1:-1]:
            bend_id = self._add_node(bend[0], bend[1], "waypoint", label=f"bend:{a}:{b}")
            self._add_edge(previous, bend_id, kind)
            previous = bend_id
        self._add_edge(previous, b, kind)

    def _wall_safe(self, points, depth: int = 0) -> list[tuple[float, float]]:
        pts = [tuple(map(float, p)) for p in points]
        if len(pts) < 2:
            return pts
        epsilon = self.scale.px(TURN_TOLERANCE_M) / (2**depth)
        simplified = rdp(pts, epsilon)
        if depth >= 4:
            return simplified
        out = [simplified[0]]
        for u, v in zip(simplified, simplified[1:]):
            if self._visible(u, v):
                out.append(v)
                continue
            i, j = _index_of(pts, u), _index_of(pts, v)
            if j - i <= 1:
                out.append(v)
                continue
            refined = self._wall_safe(pts[i : j + 1], depth + 1)
            out.extend(refined[1:])
        return out

    def _visible(self, a, b) -> bool:
        if self.barrier.is_empty:
            return True
        line = LineString([a, b])
        return not self.prepared.intersects(line)

    # ---- final simplification --------------------------------------------------------------
    def _simplify(self) -> None:
        """Remove collinear degree-2 waypoints when the merged edge stays wall-free."""
        changed = True
        while changed:
            changed = False
            adjacency: dict[str, list[str]] = {}
            for key in self.edges:
                a, b = tuple(key)
                adjacency.setdefault(a, []).append(b)
                adjacency.setdefault(b, []).append(a)
            for node in list(self.nodes.values()):
                if node.kind != "waypoint" or len(adjacency.get(node.id, [])) != 2:
                    continue
                a, b = adjacency[node.id]
                na, nb = self.nodes[a], self.nodes[b]
                va = np.array([na.x - node.x, na.y - node.y])
                vb = np.array([nb.x - node.x, nb.y - node.y])
                denom = np.linalg.norm(va) * np.linalg.norm(vb)
                cosine = float(va @ vb / denom) if denom else 1.0
                if cosine > COLLINEAR_COS:
                    continue
                if not self._visible((na.x, na.y), (nb.x, nb.y)):
                    continue
                kind = self.edges[frozenset((a, node.id))].kind
                other = self.edges[frozenset((b, node.id))].kind
                del self.edges[frozenset((a, node.id))]
                del self.edges[frozenset((b, node.id))]
                del self.nodes[node.id]
                self._add_edge(a, b, "doorway" if "doorway" in (kind, other) else "corridor")
                changed = True
                break
        for node in self.nodes.values():
            if node.label and node.label.startswith("bend:"):
                node.label = None
        # drop isolated non-semantic nodes
        connected = {n for key in self.edges for n in key}
        for node_id in [n.id for n in self.nodes.values() if n.id not in connected and n.kind in ("waypoint", "decision")]:
            del self.nodes[node_id]


def _length(path) -> float:
    pts = np.asarray(path, dtype=float)
    return float(np.sum(np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1])))) if len(pts) > 1 else 0.0


def _index_of(points, target) -> int:
    for index, p in enumerate(points):
        if p == target:
            return index
    return 0
