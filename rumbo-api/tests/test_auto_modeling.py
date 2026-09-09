from uuid import uuid4

from app.modeling.application.auto_model import AutoModelingService
from app.modeling.application.ports import StructuralParser
from app.modeling.domain.entities import MapNode, Point2D, PointOfInterest, SpatialModel
from app.modeling.domain.structural import (
    Opening,
    ProposedEdge,
    ProposedNode,
    StructuralAnalysis,
    StructuralMap,
    StructuralPoint,
    StructuralPolygon,
)
from app.modeling.domain.structural_repositories import StructuralMapRepository
from app.modeling.infrastructure.structural_parser import parse_analysis


def _rect(x0, y0, x1, y1) -> StructuralPolygon:
    return StructuralPolygon(outer=(StructuralPoint(x0, y0), StructuralPoint(x1, y0), StructuralPoint(x1, y1), StructuralPoint(x0, y1)))


class FakeParser(StructuralParser):
    """A corridor (y=100) with a room above it separated by a wall at y=50, door at x=200."""

    def __init__(self):
        self.received = {}

    def analyze(self, *, floorplan_id, content: bytes, media_type: str, pixels_per_meter=None, raster_scale=2.0) -> StructuralAnalysis:
        self.received = {"pixels_per_meter": pixels_per_meter, "raster_scale": raster_scale, "media_type": media_type}
        return StructuralAnalysis(
            structural_map=StructuralMap(
                floorplan_id=floorplan_id,
                parser="fake",
                parser_version="3",
                image_width=500,
                image_height=300,
                wall_polygons=[_rect(0, 45, 180, 55), _rect(220, 45, 500, 55)],
                obstacle_polygons=[_rect(300, 70, 310, 80)],
                doors=[Opening.create(_rect(180, 45, 220, 55), kind="door", confidence=0.9)],
            ),
            nodes=[
                ProposedNode("j1", StructuralPoint(20, 100), "decision"),
                ProposedNode("j2", StructuralPoint(200, 100), "decision"),
                ProposedNode("d1", StructuralPoint(200, 50), "door"),
                ProposedNode("r1", StructuralPoint(200, 20), "room", label="Consultorio 1", space_key="s1"),
                ProposedNode("j3", StructuralPoint(400, 100), "waypoint"),
                ProposedNode("bad", StructuralPoint(100, 20), "waypoint"),
            ],
            edges=[
                ProposedEdge("j1", "j2"),
                ProposedEdge("j2", "d1", "doorway"),
                ProposedEdge("d1", "r1", "doorway"),
                ProposedEdge("j2", "j3"),
                ProposedEdge("j1", "bad"),  # crosses the wall at y=50: must be rejected
            ],
            diagnostics={"wall_polygons": 2, "nodes": 6, "edges": 5},
        )


class FakeRepository(StructuralMapRepository):
    def __init__(self):
        self.saved = None

    def save(self, structural_map):
        self.saved = structural_map
        return structural_map


def _current_model(floorplan_id):
    old_node = uuid4()
    poi = PointOfInterest(id=uuid4(), name="Consultorio 1", category="consultorio", position=Point2D(190, 25), node_id=old_node)
    current = SpatialModel(floorplan_id=floorplan_id, pixels_per_meter=20)
    current.nodes = [MapNode(id=old_node, position=Point2D(25, 110), label="Old")]
    current.pois = [poi]
    return current


def test_auto_modeling_builds_semantic_graph_and_rejects_wall_crossing_edges():
    floorplan_id = uuid4()
    parser = FakeParser()
    repository = FakeRepository()
    service = AutoModelingService(parser, repository)

    proposal = service.propose(floorplan_id=floorplan_id, content=b"%PDF", media_type="application/pdf", current_model=_current_model(floorplan_id))

    assert repository.saved is proposal.analysis.structural_map
    assert parser.received == {"pixels_per_meter": 20, "raster_scale": 2.0, "media_type": "application/pdf"}
    kinds = sorted(node.kind for node in proposal.model.nodes)
    assert kinds == ["decision", "decision", "door", "room", "waypoint", "waypoint"]
    room = next(node for node in proposal.model.nodes if node.kind == "room")
    assert room.label == "Consultorio 1"
    assert len(proposal.navigation.edges) == 4
    assert proposal.diagnostics["edges_rejected_by_walls"] == 1
    assert {edge.kind for edge in proposal.navigation.edges} == {"corridor", "doorway"}
    # obstacles become wall segments too, so routing can never cross a column
    assert len(proposal.model.walls) == 12
    assert proposal.model.pixels_per_meter == 20


def test_poi_is_reattached_to_room_anchor():
    floorplan_id = uuid4()
    proposal = AutoModelingService(FakeParser(), FakeRepository()).propose(
        floorplan_id=floorplan_id, content=b"x", media_type="image/png", current_model=_current_model(floorplan_id)
    )
    room = next(node for node in proposal.model.nodes if node.kind == "room")
    assert proposal.model.pois[0].node_id == room.id


def test_parse_analysis_reads_v3_payload():
    payload = {
        "parser": "rumbo-structural-mapper",
        "parser_version": "3",
        "image_size": {"width": 100, "height": 80},
        "scale": {"pixels_per_meter": 20.5, "source": "estimated"},
        "walls": [{"outer": [[0, 0], [10, 0], [10, 5], [0, 5]], "holes": []}],
        "obstacles": [{"outer": [[20, 20], [24, 20], [24, 24], [20, 24]], "holes": []}],
        "windows": [],
        "openings": [
            {"id": "o1", "kind": "entrance", "polygon": {"outer": [[0, 0], [4, 0], [4, 2], [0, 2]], "holes": []}, "center": [2, 1], "width_px": 4, "confidence": 0.8, "spaces": ["s1", None], "sources": ["gap", "swing"]}
        ],
        "spaces": [{"id": "s1", "kind": "circulation", "label": "Pasillo", "polygon": {"outer": [[0, 0], [50, 0], [50, 50], [0, 50]], "holes": []}, "openings": ["o1"], "confidence": 0.9}],
        "walkable": [{"polygon": {"outer": [[1, 1], [49, 1], [49, 49], [1, 49]], "holes": []}, "kind": "walkable"}],
        "graph": {
            "nodes": [{"id": "n1", "x": 2, "y": 1, "kind": "entrance"}, {"id": "n2", "x": 25, "y": 25, "kind": "decision"}],
            "edges": [{"from": "n1", "to": "n2", "kind": "doorway", "length_px": 30}],
        },
        "validation": {"status": "warnings", "issues": [{"code": "no-entrance", "severity": "warning", "message": "x", "subjects": []}], "metrics": {"nodes": 2}},
        "diagnostics": {"backend": "classical-morphology", "nodes": 2},
    }
    analysis = parse_analysis(uuid4(), payload)
    structural = analysis.structural_map
    assert structural.parser_version == "3"
    assert structural.estimated_pixels_per_meter == 20.5 and structural.scale_source == "estimated"
    assert len(structural.obstacle_polygons) == 1
    assert structural.doors[0].kind == "entrance" and structural.doors[0].space_keys == ("s1", None)
    assert structural.spaces[0].label == "Pasillo" and structural.spaces[0].kind == "circulation"
    assert structural.validation.status == "warnings" and structural.validation.issues[0].code == "no-entrance"
    assert analysis.edges[0].kind == "doorway"
    assert analysis.diagnostics["backend"] == "classical-morphology"
