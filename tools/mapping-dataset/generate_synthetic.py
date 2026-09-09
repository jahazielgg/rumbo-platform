#!/usr/bin/env python3
"""Generate small rectilinear clinic floorplans with perfect structural/navigation labels.

The source of truth is geometry, not the rendered image. Each case emits:
- SVG floorplan for training/rasterization;
- JSON walls, doors, rooms, POIs and navigation ground truth.

Usage:
    python tools/mapping-dataset/generate_synthetic.py --count 100 --output datasets/rumbo_mapping/synthetic
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float


@dataclass
class Door:
    x: float
    y: float
    width: float
    orientation: str
    room_id: str


@dataclass
class Node:
    id: str
    x: float
    y: float
    kind: str


def generate(seed: int) -> dict:
    rng = random.Random(seed)
    width = rng.choice([36.0, 42.0, 48.0])
    height = rng.choice([22.0, 26.0, 30.0])
    corridor_y = height / 2
    corridor_h = rng.uniform(2.2, 3.2)
    room_depth = (height - corridor_h) / 2
    room_count = rng.randint(5, 8)
    bay = width / room_count

    rooms = []
    doors: list[Door] = []
    pois = []
    nodes: list[Node] = [Node("entry", 1.0, corridor_y, "entrance")]
    edges: list[dict] = []

    corridor_nodes = ["entry"]
    for index in range(room_count):
        x = index * bay
        top_id = f"room_top_{index}"
        bottom_id = f"room_bottom_{index}"
        top = Rect(x + 0.2, 0.2, bay - 0.4, room_depth - 0.2)
        bottom = Rect(x + 0.2, corridor_y + corridor_h / 2, bay - 0.4, room_depth - 0.2)
        rooms.extend([
            {"id": top_id, "kind": "consultorio", "rect": asdict(top)},
            {"id": bottom_id, "kind": rng.choice(["consultorio", "laboratorio", "servicio"]), "rect": asdict(bottom)},
        ])
        door_x = x + bay / 2
        doors.append(Door(door_x, corridor_y - corridor_h / 2, 0.9, "horizontal", top_id))
        doors.append(Door(door_x, corridor_y + corridor_h / 2, 0.9, "horizontal", bottom_id))
        junction_id = f"j{index}"
        nodes.append(Node(junction_id, door_x, corridor_y, "decision"))
        corridor_nodes.append(junction_id)
        for suffix, room_id, door_y in (("t", top_id, corridor_y - corridor_h / 2), ("b", bottom_id, corridor_y + corridor_h / 2)):
            door_node = f"d{index}{suffix}"
            nodes.append(Node(door_node, door_x, door_y, "waypoint"))
            edges.append({"from": junction_id, "to": door_node})
            pois.append({
                "id": f"poi_{room_id}",
                "name": f"{rooms[-2 if suffix == 't' else -1]['kind'].title()} {index + 1}{suffix.upper()}",
                "room_id": room_id,
                "node_id": door_node,
                "x": door_x,
                "y": top.y + top.h / 2 if suffix == "t" else bottom.y + bottom.h / 2,
            })

    exit_node = "exit"
    nodes.append(Node(exit_node, width - 1.0, corridor_y, "entrance"))
    corridor_nodes.append(exit_node)
    for left, right in zip(corridor_nodes, corridor_nodes[1:]):
        edges.append({"from": left, "to": right})

    return {
        "schema_version": 1,
        "seed": seed,
        "canvas_meters": {"width": width, "height": height},
        "corridor": {"center_y": corridor_y, "width": corridor_h},
        "rooms": rooms,
        "doors": [asdict(item) for item in doors],
        "pois": pois,
        "navigation": {"nodes": [asdict(item) for item in nodes], "edges": edges},
    }


def svg(case: dict, px_per_meter: int = 28) -> str:
    width = case["canvas_meters"]["width"]
    height = case["canvas_meters"]["height"]
    w = round(width * px_per_meter)
    h = round(height * px_per_meter)

    def sx(value: float) -> float:
        return value * px_per_meter

    items = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">', '<rect width="100%" height="100%" fill="#fffdf8"/>']
    for room in case["rooms"]:
        rect = room["rect"]
        items.append(
            f'<rect x="{sx(rect["x"]):.1f}" y="{sx(rect["y"]):.1f}" width="{sx(rect["w"]):.1f}" height="{sx(rect["h"]):.1f}" fill="#faf7f0" stroke="#1f2329" stroke-width="8"/>'
        )
        items.append(
            f'<text x="{sx(rect["x"] + rect["w"] / 2):.1f}" y="{sx(rect["y"] + rect["h"] / 2):.1f}" text-anchor="middle" font-family="Arial" font-size="18" fill="#333">{room["kind"].title()}</text>'
        )
    # Cover short wall sections with white to create explicit door openings.
    for door in case["doors"]:
        if door["orientation"] == "horizontal":
            items.append(
                f'<line x1="{sx(door["x"] - door["width"] / 2):.1f}" y1="{sx(door["y"]):.1f}" x2="{sx(door["x"] + door["width"] / 2):.1f}" y2="{sx(door["y"]):.1f}" stroke="#fffdf8" stroke-width="12"/>'
            )
            items.append(
                f'<path d="M {sx(door["x"] - door["width"] / 2):.1f},{sx(door["y"]):.1f} A {sx(door["width"]):.1f},{sx(door["width"]):.1f} 0 0 1 {sx(door["x"] + door["width"] / 2):.1f},{sx(door["y"] - door["width"]):.1f}" fill="none" stroke="#777" stroke-width="2"/>'
            )
    items.append('</svg>')
    return "\n".join(items)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("datasets/rumbo_mapping/synthetic"))
    parser.add_argument("--seed", type=int, default=180)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for index in range(args.count):
        seed = args.seed + index
        case = generate(seed)
        stem = f"clinic_{seed:05d}"
        (args.output / f"{stem}.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        (args.output / f"{stem}.svg").write_text(svg(case), encoding="utf-8")
    print(f"Generated {args.count} synthetic clinics in {args.output}")


if __name__ == "__main__":
    main()
