from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from uuid import UUID, uuid4

from app.navigation.domain.entities import NavigationConfig, NavigationEdge
from app.shared_kernel.errors import ValidationError
from app.shared_kernel.geometry import segments_properly_cross

from .ports import StructuralParser
from ..domain.entities import MapNode, Point2D, PointOfInterest, SpatialModel, WallSegment
from ..domain.structural import NODE_KINDS, StructuralAnalysis, StructuralPolygon
from ..domain.structural_repositories import StructuralMapRepository

LABEL_PREFIX = {
    "decision": "G",
    "waypoint": "N",
    "door": "P",
    "entrance": "E",
    "room": "S",
    "connector": "C",
}
MAX_WALL_SEGMENTS = 4000


@dataclass(slots=True)
class AutoModelProposal:
    model: SpatialModel
    navigation: NavigationConfig
    analysis: StructuralAnalysis
    diagnostics: dict[str, int | float | str] = field(default_factory=dict)


class AutoModelingService:
    """Translate the structural scene into Rumbo's editable spatial/navigation model.

    Perception and geometry happen in the structural mapper. This service owns the
    conversion into domain entities, re-checks the hard invariant (no edge crosses a
    wall or obstacle) against the exact segments the editor will persist, and reattaches
    the administrator's POIs to the new graph.
    """

    def __init__(self, parser: StructuralParser, structural_repository: StructuralMapRepository):
        self.parser = parser
        self.structural_repository = structural_repository

    def propose(
        self,
        *,
        floorplan_id: UUID,
        content: bytes,
        media_type: str,
        current_model: SpatialModel,
        raster_scale: float = 2.0,
    ) -> AutoModelProposal:
        analysis = self.parser.analyze(
            floorplan_id=floorplan_id,
            content=content,
            media_type=media_type,
            pixels_per_meter=current_model.pixels_per_meter,
            raster_scale=raster_scale,
        )
        self.structural_repository.save(analysis.structural_map)
        if len(analysis.nodes) < 2:
            raise ValidationError(
                "El parser entendió la estructura, pero no pudo obtener una red transitable suficiente. Revisa paredes/puertas manualmente."
            )

        structural = analysis.structural_map
        walls = self._wall_segments(structural.wall_polygons + structural.obstacle_polygons + structural.window_polygons)

        nodes: list[MapNode] = []
        node_ids: dict[str, UUID] = {}
        counters: dict[str, int] = {}
        for proposed in analysis.nodes:
            kind = proposed.kind if proposed.kind in NODE_KINDS else "waypoint"
            counters[kind] = counters.get(kind, 0) + 1
            label = proposed.label.strip() if proposed.label and proposed.label.strip() else f"{LABEL_PREFIX[kind]}{counters[kind]}"
            node_id = uuid4()
            node_ids[proposed.key] = node_id
            nodes.append(MapNode(id=node_id, position=Point2D(x=proposed.position.x, y=proposed.position.y), label=label, kind=kind))
        positions = {node.id: node.position for node in nodes}

        edges: list[NavigationEdge] = []
        seen: set[frozenset[UUID]] = set()
        rejected = 0
        for proposed in analysis.edges:
            a = node_ids.get(proposed.from_key)
            b = node_ids.get(proposed.to_key)
            if not a or not b or a == b:
                continue
            key = frozenset((a, b))
            if key in seen:
                continue
            seen.add(key)
            if self._crosses_wall(positions[a], positions[b], walls):
                rejected += 1
                continue
            edges.append(
                NavigationEdge(
                    id=uuid4(),
                    from_node_id=a,
                    to_node_id=b,
                    kind="doorway" if proposed.kind == "doorway" else "corridor",
                    accessible=True,
                )
            )
        if not edges:
            raise ValidationError("No se pudo construir una red conectada a partir del espacio transitable.")

        pois = [self._reattach_poi(poi, nodes) for poi in current_model.pois]
        model = SpatialModel(
            floorplan_id=floorplan_id,
            pixels_per_meter=current_model.pixels_per_meter,
            walls=walls,
            nodes=nodes,
            pois=pois,
        )
        navigation = NavigationConfig(floorplan_id=floorplan_id, edges=edges, vertical_connectors=[])
        diagnostics: dict[str, int | float | str] = dict(analysis.diagnostics)
        diagnostics["edges_rejected_by_walls"] = rejected
        diagnostics["validation_status"] = structural.validation.status
        if structural.estimated_pixels_per_meter and not current_model.pixels_per_meter:
            diagnostics["estimated_pixels_per_meter"] = round(structural.estimated_pixels_per_meter, 3)
        return AutoModelProposal(model=model, navigation=navigation, analysis=analysis, diagnostics=diagnostics)

    @staticmethod
    def _crosses_wall(a: Point2D, b: Point2D, walls: list[WallSegment]) -> bool:
        return any(
            segments_properly_cross(a.x, a.y, b.x, b.y, wall.start.x, wall.start.y, wall.end.x, wall.end.y)
            for wall in walls
        )

    @staticmethod
    def _reattach_poi(poi: PointOfInterest, nodes: list[MapNode]) -> PointOfInterest:
        """Prefer a room/connector anchor near the POI; otherwise the nearest node."""

        def distance(node: MapNode) -> float:
            return hypot(node.position.x - poi.position.x, node.position.y - poi.position.y)

        anchors = [node for node in nodes if node.kind in ("room", "connector")]
        nearest_any = min(nodes, key=distance)
        chosen = nearest_any
        if anchors:
            nearest_anchor = min(anchors, key=distance)
            if distance(nearest_anchor) <= 2.5 * max(distance(nearest_any), 1.0):
                chosen = nearest_anchor
        return PointOfInterest(id=poi.id, name=poi.name, category=poi.category, position=poi.position, node_id=chosen.id)

    @staticmethod
    def _wall_segments(polygons: list[StructuralPolygon]) -> list[WallSegment]:
        segments: list[WallSegment] = []
        seen: set[tuple[int, int, int, int]] = set()
        for polygon in polygons:
            rings = [polygon.outer, *polygon.holes]
            for ring in rings:
                if len(ring) < 2:
                    continue
                for index, start in enumerate(ring):
                    end = ring[(index + 1) % len(ring)]
                    if hypot(end.x - start.x, end.y - start.y) < 2:
                        continue
                    key = tuple(round(value / 2) for value in (start.x, start.y, end.x, end.y))
                    reverse = (key[2], key[3], key[0], key[1])
                    if key in seen or reverse in seen:
                        continue
                    seen.add(key)
                    segments.append(WallSegment(id=uuid4(), start=Point2D(x=start.x, y=start.y), end=Point2D(x=end.x, y=end.y)))
        return segments[:MAX_WALL_SEGMENTS]
