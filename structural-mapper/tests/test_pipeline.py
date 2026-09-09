import networkx as nx
from shapely.geometry import LineString
from shapely.ops import unary_union

from mapper.pipeline import MapperOptions, Pipeline, scene_to_payload


def _scene(synthetic_case, ppm_hint=None):
    _, svg, ppm = synthetic_case
    options = MapperOptions(pixels_per_meter=(ppm * 2) if ppm_hint is None else ppm_hint, raster_scale=2.0, use_ml=False)
    return Pipeline().run_bytes(svg, "image/svg+xml", options)


def test_synthetic_clinic_is_fully_understood(synthetic_case):
    case, _, _ = synthetic_case
    scene = _scene(synthetic_case)
    rooms = [s for s in scene.spaces if s.kind == "room"]
    circulation = [s for s in scene.spaces if s.kind == "circulation"]
    doors = [o for o in scene.openings if o.kind == "door"]
    entrances = [o for o in scene.openings if o.kind == "entrance"]

    assert len(rooms) == len(case["rooms"])
    assert len(circulation) == 1
    assert len(doors) == len(case["doors"])
    assert len(entrances) == 2  # both cropped corridor ends
    assert all(room.label for room in rooms)
    assert scene.validation.status in ("ok", "warnings")
    assert scene.validation.metrics["edges_crossing_walls"] == 0


def test_graph_is_minimal_semantic_and_topologically_correct(synthetic_case):
    case, _, _ = synthetic_case
    scene = _scene(synthetic_case)
    graph = scene.graph
    kinds = {}
    for node in graph.nodes:
        kinds[node.kind] = kinds.get(node.kind, 0) + 1
    assert kinds["room"] == len(case["rooms"])
    assert kinds["door"] == len(case["doors"])
    assert kinds["entrance"] == 2
    # one junction per door pair on the corridor, no dense grid
    assert len(graph.nodes) < 3 * len(case["doors"]) + 10

    g = nx.Graph()
    g.add_nodes_from(n.id for n in graph.nodes)
    g.add_edges_from((e.from_id, e.to_id) for e in graph.edges)
    assert nx.is_connected(g)

    barrier = unary_union([w.polygon for w in scene.walls]).buffer(-0.75)
    by_id = {n.id: n for n in graph.nodes}
    for edge in graph.edges:
        a, b = by_id[edge.from_id], by_id[edge.to_id]
        assert not barrier.intersects(LineString([(a.x, a.y), (b.x, b.y)])), f"edge {edge.from_id}-{edge.to_id} crosses a wall"
    # every room is entered through a doorway edge
    door_edges = [e for e in graph.edges if e.kind == "doorway"]
    assert len(door_edges) >= len(case["doors"])


def test_scale_is_estimated_when_unknown(synthetic_case):
    scene = _scene(synthetic_case, ppm_hint=0)
    assert scene.scale.source == "estimated"
    assert 30 <= scene.scale.pixels_per_meter <= 120


def test_payload_serialization_contract(synthetic_case):
    scene = _scene(synthetic_case)
    payload = scene_to_payload(scene)
    assert payload["parser_version"] == "3"
    assert payload["image_size"] == {"width": scene.width, "height": scene.height}
    assert {"walls", "obstacles", "windows", "openings", "spaces", "walkable", "graph", "validation", "diagnostics", "scale"} <= payload.keys()
    node = payload["graph"]["nodes"][0]
    assert {"id", "x", "y", "kind"} <= node.keys()
    assert payload["validation"]["status"] in ("ok", "warnings", "errors")
