"""Raster medial axis -> topological graph.

The skeleton of the walkable circulation is the natural set of corridor centre-lines.
This module converts it into a `networkx.Graph` whose nodes are junctions/endpoints and
whose edges carry the pixel path between them, then prunes and simplifies that graph
without ever leaving the walkable area.
"""
from __future__ import annotations

from collections import defaultdict

import cv2
import networkx as nx
import numpy as np
from skimage.morphology import skeletonize

NEIGHBOURS = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


def skeleton_graph(mask: np.ndarray) -> nx.Graph:
    """Build a graph from a binary mask. Node attrs: x, y. Edge attrs: path, length."""
    skel = skeletonize(mask.astype(bool))
    h, w = skel.shape
    ys, xs = np.nonzero(skel)
    graph = nx.Graph()
    if xs.size == 0:
        return graph
    pixels = set(zip(xs.tolist(), ys.tolist()))

    def neighbours(p):
        x, y = p
        return [(x + dx, y + dy) for dx, dy in NEIGHBOURS if (x + dx, y + dy) in pixels]

    degree = {p: len(neighbours(p)) for p in pixels}
    key_pixels = {p for p, d in degree.items() if d != 2}
    if not key_pixels:  # a pure loop: pick an arbitrary pixel as the only node
        key_pixels = {next(iter(pixels))}

    # cluster adjacent key pixels (junction blobs) into single nodes
    cluster_of: dict[tuple[int, int], int] = {}
    clusters: list[list[tuple[int, int]]] = []
    for p in key_pixels:
        if p in cluster_of:
            continue
        stack = [p]
        cluster_of[p] = len(clusters)
        members = []
        while stack:
            q = stack.pop()
            members.append(q)
            for n in neighbours(q):
                if n in key_pixels and n not in cluster_of:
                    cluster_of[n] = len(clusters)
                    stack.append(n)
        clusters.append(members)
    for index, members in enumerate(clusters):
        cx = float(np.mean([m[0] for m in members]))
        cy = float(np.mean([m[1] for m in members]))
        graph.add_node(index, x=cx, y=cy, pixels=members)

    visited_edges: set[frozenset] = set()
    for index, members in enumerate(clusters):
        for start in members:
            for nxt in neighbours(start):
                if nxt in key_pixels:
                    if cluster_of[nxt] != index:
                        pair = frozenset((index, cluster_of[nxt]))
                        if pair not in visited_edges:
                            visited_edges.add(pair)
                            _add_edge(graph, index, cluster_of[nxt], [start, nxt])
                    continue
                path = [start, nxt]
                prev, cur = start, nxt
                while cur not in key_pixels:
                    options = [n for n in neighbours(cur) if n != prev and n not in path[-3:]]
                    if not options:
                        break
                    prev, cur = cur, options[0]
                    path.append(cur)
                if cur in key_pixels:
                    target = cluster_of[cur]
                    signature = frozenset(path[1:-1]) if len(path) > 2 else frozenset(path)
                    if (target, index, signature) in visited_edges or (index, target, signature) in visited_edges:
                        continue
                    visited_edges.add((index, target, signature))
                    _add_edge(graph, index, target, path)
    return graph


def _path_length(path) -> float:
    pts = np.asarray(path, dtype=float)
    if len(pts) < 2:
        return 0.0
    return float(np.sum(np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))))


def _add_edge(graph: nx.Graph, a: int, b: int, path) -> None:
    length = _path_length(path)
    if a == b:
        return  # self loops carry no routing information
    if graph.has_edge(a, b):
        if graph[a][b]["length"] <= length:
            return
    graph.add_edge(a, b, path=list(path), length=length)


def prune_spurs(graph: nx.Graph, min_length: float, protected: set[int] | None = None, local_width=None) -> nx.Graph:
    """Iteratively remove short dead-end branches.

    Besides noise, the medial axis of any wide hall grows a branch towards every corner
    whose length is about the hall's half-width. `local_width(x, y)` (distance to the
    nearest wall at the junction) lets those corner branches be pruned proportionally.
    """
    protected = protected or set()
    changed = True
    while changed:
        changed = False
        for node in list(graph.nodes):
            if node in protected or graph.degree(node) != 1:
                continue
            (neighbour,) = graph.neighbors(node)
            threshold = min_length
            if local_width is not None:
                threshold = max(threshold, 1.6 * local_width(graph.nodes[neighbour]["x"], graph.nodes[neighbour]["y"]))
            if graph[node][neighbour]["length"] < threshold:
                graph.remove_node(node)
                changed = True
        collapse_degree_two(graph, protected)
    return graph


def collapse_degree_two(graph: nx.Graph, protected: set[int] | None = None) -> None:
    """Merge chains through unprotected degree-2 nodes into single edges."""
    protected = protected or set()
    for node in list(graph.nodes):
        if node in protected or node not in graph or graph.degree(node) != 2:
            continue
        a, b = list(graph.neighbors(node))
        if a == b:
            continue
        pa = graph[a][node]["path"]
        pb = graph[node][b]["path"]
        pa = pa if _near(pa[-1], graph.nodes[node]) else pa[::-1]
        pb = pb if _near(pb[0], graph.nodes[node]) else pb[::-1]
        merged = list(pa) + list(pb[1:])
        graph.remove_node(node)
        if graph.has_edge(a, b):
            if graph[a][b]["length"] <= _path_length(merged):
                continue
        graph.add_edge(a, b, path=merged, length=_path_length(merged))


def _near(pixel, node_attrs) -> bool:
    return abs(pixel[0] - node_attrs["x"]) <= 2 and abs(pixel[1] - node_attrs["y"]) <= 2


def merge_close_nodes(graph: nx.Graph, distance: float, protected: set[int] | None = None) -> None:
    """Contract junction nodes that are closer than `distance` (skeleton double-junctions)."""
    protected = protected or set()
    changed = True
    while changed:
        changed = False
        for a, b, data in list(graph.edges(data=True)):
            if a in protected or b in protected or a not in graph or b not in graph:
                continue
            if data["length"] >= distance:
                continue
            if graph.degree(a) < 3 or graph.degree(b) < 3:
                continue
            ax, ay = graph.nodes[a]["x"], graph.nodes[a]["y"]
            bx, by = graph.nodes[b]["x"], graph.nodes[b]["y"]
            for n in list(graph.neighbors(b)):
                if n == a:
                    continue
                path = graph[b][n]["path"]
                path = path if _near(path[0], graph.nodes[b]) else path[::-1]
                new_path = [((ax + bx) / 2, (ay + by) / 2)] + list(path)
                if graph.has_edge(a, n):
                    continue
                graph.add_edge(a, n, path=new_path, length=_path_length(new_path))
            graph.nodes[a]["x"], graph.nodes[a]["y"] = (ax + bx) / 2, (ay + by) / 2
            graph.remove_node(b)
            changed = True
            break


def rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return list(points)
    pts = np.asarray(points, dtype=float)
    start, end = pts[0], pts[-1]
    line = end - start
    norm = np.hypot(*line)
    if norm == 0:
        distances = np.hypot(*(pts - start).T)
    else:
        rel = pts - start
        distances = np.abs(line[0] * rel[:, 1] - line[1] * rel[:, 0]) / norm
    index = int(np.argmax(distances))
    if distances[index] > epsilon:
        left = rdp(points[: index + 1], epsilon)
        right = rdp(points[index:], epsilon)
        return left[:-1] + right
    return [tuple(points[0]), tuple(points[-1])]
