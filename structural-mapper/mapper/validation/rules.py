"""Hard navigation invariants, evaluated on every proposal.

Errors block publication in the API (the admin must fix them); warnings are shown.
"""
from __future__ import annotations

import networkx as nx
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep

from ..contracts import Scene, ValidationIssue, ValidationReport


def validate(scene: Scene) -> ValidationReport:
    report = ValidationReport()
    graph = scene.graph
    nodes = {n.id: n for n in graph.nodes}
    barrier = unary_union([w.polygon for w in scene.walls]).buffer(-0.25) if scene.walls else None
    prepared = prep(barrier) if barrier is not None and not barrier.is_empty else None

    crossing = []
    for edge in graph.edges:
        a, b = nodes.get(edge.from_id), nodes.get(edge.to_id)
        if a is None or b is None:
            report.add(ValidationIssue("dangling-edge", "error", "Edge references a missing node.", [edge.from_id, edge.to_id]))
            continue
        if prepared is not None and prepared.intersects(LineString([(a.x, a.y), (b.x, b.y)])):
            crossing.append(f"{a.id}-{b.id}")
    if crossing:
        report.add(ValidationIssue("edge-crosses-wall", "error", f"{len(crossing)} edges cross a wall or obstacle.", crossing))
    report.metrics["edges_crossing_walls"] = len(crossing)

    g = nx.Graph()
    g.add_nodes_from(nodes)
    g.add_edges_from((e.from_id, e.to_id) for e in graph.edges)
    components = list(nx.connected_components(g)) if nodes else []
    report.metrics["components"] = len(components)
    isolated = [n for n in nodes if g.degree(n) == 0]
    if isolated:
        report.add(ValidationIssue("isolated-node", "warning", f"{len(isolated)} nodes have no connections.", isolated))
    if len(components) > 1:
        largest = max(components, key=len)
        others = [n for c in components if c is not largest for n in c]
        report.add(ValidationIssue("disconnected-graph", "warning", f"Graph has {len(components)} components; {len(others)} nodes are unreachable from the main network.", others))

    entrances = [n.id for n in graph.nodes if n.kind == "entrance"]
    report.metrics["entrances"] = len(entrances)
    if not entrances:
        report.add(ValidationIssue("no-entrance", "warning", "No entrance was detected; mark one manually so routes can start outside.", []))
    else:
        reachable = set()
        for e in entrances:
            if e in g:
                reachable |= nx.node_connected_component(g, e)
        rooms = [n for n in graph.nodes if n.kind in ("room", "connector")]
        unreachable = [n.id for n in rooms if n.id not in reachable]
        report.metrics["rooms_unreachable_from_entrance"] = len(unreachable)
        if unreachable:
            report.add(ValidationIssue("room-unreachable", "warning", f"{len(unreachable)} rooms cannot be reached from any entrance.", unreachable))

    with_nodes = {n.space_id for n in graph.nodes if n.space_id}
    silent = [s.id for s in scene.spaces if s.kind in ("room", "vertical") and s.id not in with_nodes]
    report.metrics["spaces_without_node"] = len(silent)
    if silent:
        report.add(ValidationIssue("space-without-access", "warning", f"{len(silent)} spaces have no detected door; add an opening if they are reachable.", silent))

    represented = {n.opening_id for n in graph.nodes if n.opening_id}
    missing = [o.id for o in scene.openings if o.id not in represented]
    if missing:
        report.add(ValidationIssue("opening-without-node", "warning", f"{len(missing)} openings are not represented as transitions.", missing))

    # degree-2 collinear leftovers
    leftovers = 0
    for node in graph.nodes:
        if node.kind != "waypoint" or g.degree(node.id) != 2:
            continue
        a, b = list(g.neighbors(node.id))
        na, nb = nodes[a], nodes[b]
        va = (na.x - node.x, na.y - node.y)
        vb = (nb.x - node.x, nb.y - node.y)
        la = (va[0] ** 2 + va[1] ** 2) ** 0.5
        lb = (vb[0] ** 2 + vb[1] ** 2) ** 0.5
        if la and lb and (va[0] * vb[0] + va[1] * vb[1]) / (la * lb) < -0.985:
            leftovers += 1
    report.metrics["collinear_waypoints"] = leftovers
    if leftovers:
        report.add(ValidationIssue("collinear-waypoint", "info", f"{leftovers} collinear waypoints remain (kept to avoid wall crossings).", []))

    low = [o.id for o in scene.openings if o.confidence < 0.6]
    if low:
        report.add(ValidationIssue("low-confidence-opening", "info", f"{len(low)} openings have low confidence; verify them.", low))
    report.metrics["nodes"] = len(nodes)
    report.metrics["edges"] = len(graph.edges)
    return report
