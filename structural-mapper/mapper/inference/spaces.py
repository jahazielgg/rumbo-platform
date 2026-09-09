"""Partition the interior into spaces and give them architectural meaning.

Deterministic rules, not learned:

* the building envelope is the concave hull of the wall structure, so plans with margins,
  title blocks or cropped corridors are handled the same way;
* free pixels inside the envelope, separated by walls *and* openings, are spaces;
* an opening is only kept if it separates two different spaces (or a space and the
  exterior); anything else (text mistaken for a door, a symbol inside a room) is dropped;
* circulation vs room is decided by door count, shape and labels;
* labels also reveal vertical connectors (elevator/stairs/ramp) and voids.
"""
from __future__ import annotations

import re
from itertools import count

import cv2
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..contracts import Opening, Scale, Space, TextLabel, WallElement
from ..reconstruction.openings import MAX_DOOR_M, swing_evidence
from ..geometry import components, line_closing, mask_to_polygons, oriented_box, rasterize, segment

CIRCULATION_WORDS = re.compile(r"\b(pasillo|pasadizo|corredor|corridor|hall|vest[ií]bulo|lobby|espera|recepci[oó]n|reception|circulaci[oó]n|atrio|foyer)\b", re.IGNORECASE)
VERTICAL_WORDS = {
    "elevator": re.compile(r"\b(ascensor(?:es)?|elevador|elevator|lift)\b", re.IGNORECASE),
    "stairs": re.compile(r"\b(escalera[s]?|stair[s]?|staircase)\b", re.IGNORECASE),
    "ramp": re.compile(r"\b(rampa|ramp)\b", re.IGNORECASE),
}
VOID_WORDS = re.compile(r"\b(patio|jard[ií]n|garden|ducto|shaft|vac[ií]o|void|terraza)\b", re.IGNORECASE)
MAX_ENTRANCE_M = 6.0
SEAL_M = 8.0  # widest gap sealed when separating inside from outside


class SpaceInference:
    def __init__(self, scale: Scale, shape: tuple[int, int], thin: np.ndarray | None = None):
        self.scale = scale
        self.shape = shape
        self.thin = thin
        self.glass: list[WallElement] = []  # wide exterior gaps that are glazing, not entrances

    def run(self, walls: list[WallElement], openings: list[Opening], labels: list[TextLabel]) -> tuple[list[Space], list[Opening], dict]:
        blocked = rasterize([w.polygon for w in walls], self.shape)
        exterior = self._exterior(walls)
        hull_mask = ~exterior
        opening_mask = rasterize([o.polygon for o in openings], self.shape, dilate_px=max(1, int(round(self.scale.px(0.12)))))
        free = ~blocked & ~opening_mask & hull_mask

        spaces: list[Space] = []
        label_image = np.zeros(self.shape, dtype=np.int32)
        min_area = self.scale.px(0.8) ** 2
        ids = count(1)
        entrance_candidates: list[Opening] = []
        for component, stats, _ in components(free, min_area=min_area):
            polygons = mask_to_polygons(component, simplify_px=max(1.0, self.scale.px(0.04)), min_area=min_area)
            if not polygons:
                continue
            polygon = max(polygons, key=lambda p: p.area)
            space_id = f"s{next(ids)}"
            label_image[component] = int(space_id[1:])
            area = float(stats[cv2.CC_STAT_AREA])
            distance = cv2.distanceTransform(component.astype(np.uint8), cv2.DIST_L2, 5)
            radius = float(distance.max())
            ys, xs = np.nonzero(component)
            _, long_side, short_side, _, _ = oriented_box(np.column_stack((xs, ys)))
            space = Space(
                id=space_id,
                polygon=polygon,
                area_px=area,
                narrowness=radius / max(np.sqrt(area), 1.0),
                elongation=long_side / max(short_side, 1.0),
            )
            spaces.append(space)
            entrance_candidates.extend(self._exterior_contacts(component, exterior, space, ids_source=len(entrance_candidates)))

        openings = self._assign_openings(openings, entrance_candidates, label_image, exterior, spaces)
        self._label(spaces, labels)
        self._classify(spaces, openings)
        masks = {"blocked": blocked, "hull": hull_mask, "labels": label_image}
        return spaces, openings, masks

    # ---- envelope ----------------------------------------------------------------------
    def _exterior(self, walls: list[WallElement]) -> np.ndarray:
        """Exterior = free space reachable from the image border once every gap narrower
        than the largest plausible entrance has been sealed.

        Sealing uses oriented line closings on the wall mask, so doors, windows and cropped
        corridor ends are bridged while the outside contour of the building is untouched.
        Plans without margins simply have (almost) no exterior; their open corridor ends
        are recovered as entrances from border contact.
        """
        blocked = rasterize([w.polygon for w in self._dominant_structure(walls)], self.shape)
        sealed = line_closing(blocked, self.scale.px(SEAL_M))
        free = (~sealed).astype(np.uint8)
        count, labels, _, _ = cv2.connectedComponentsWithStats(free, 8)
        border = np.zeros(self.shape, dtype=bool)
        border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
        touching = set(np.unique(labels[border])) - {0}
        if not touching:
            return np.zeros(self.shape, dtype=bool)
        return np.isin(labels, list(touching))

    def _dominant_structure(self, walls: list[WallElement]) -> list[WallElement]:
        """Drop scale bars, north arrows and legends: structure far from the main cluster."""
        if len(walls) <= 1:
            return walls
        grow = self.scale.px(2.0)
        clusters = unary_union([w.polygon.buffer(grow) for w in walls])
        if clusters.geom_type == "Polygon":
            return walls
        main = max(clusters.geoms, key=lambda p: p.area)
        return [w for w in walls if w.polygon.intersects(main)]

    # ---- entrances (spaces touching the outside) -------------------------------------
    def _exterior_contacts(self, component: np.ndarray, exterior: np.ndarray, space: Space, ids_source: int) -> list[Opening]:
        """Entrances where a space meets the exterior or the image border."""
        ring = cv2.dilate(component.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        contact = ring & exterior
        border = np.zeros_like(component)
        border[0, :] = border[-1, :] = True
        border[:, 0] = border[:, -1] = True
        contact |= component & border
        result: list[Opening] = []
        perimeter_contact = 0.0
        for part, stats, centroid in components(contact, min_area=2):
            ys, xs = np.nonzero(part)
            if xs.size < 2:
                continue
            center, long_side, short_side, axis, box = oriented_box(np.column_stack((xs, ys)))
            width = max(long_side, 1.0)
            perimeter_contact += width
            normal = np.array([-axis[1], axis[0]])
            probe = (center[0] + normal[0] * 3, center[1] + normal[1] * 3)
            if not self._inside(component, probe):
                normal = -normal
            touches_border = bool((part & border).any())
            evidence = swing_evidence(self.thin, center, (float(normal[0]), float(normal[1])), width, self.scale) if self.thin is not None else 0.0
            limit = MAX_ENTRANCE_M if (touches_border or evidence > 0) else MAX_DOOR_M
            if width < self.scale.px(0.5):
                continue
            depth = max(2.0, self.scale.px(0.2))
            if width > self.scale.px(limit):
                # A wide gap in the exterior wall without door evidence is glazing.
                self.glass.append(WallElement(polygon=segment(center, axis, width).buffer(depth, cap_style="flat"), kind="window", confidence=0.5))
                continue
            result.append(
                Opening(
                    id=f"e{ids_source + len(result) + 1}",
                    polygon=segment(center, axis, width).buffer(depth / 2, cap_style="flat"),
                    center=center,
                    axis=segment(center, axis, width),
                    normal=(float(normal[0]), float(normal[1])),
                    width_px=width,
                    kind="entrance",
                    confidence=0.8 if evidence > 0 else 0.5,
                    space_ids=(space.id, None),
                    sources=("envelope", "swing") if evidence > 0 else ("envelope",),
                )
            )
        if perimeter_contact > 0.5 * space.polygon.exterior.length:
            space.kind = "void"  # mostly open to the outside: not a usable room
            space.confidence = 0.3
            return []
        return result

    def _inside(self, component: np.ndarray, point: tuple[float, float]) -> bool:
        x, y = int(round(point[0])), int(round(point[1]))
        return 0 <= y < component.shape[0] and 0 <= x < component.shape[1] and bool(component[y, x])

    # ---- opening <-> space assignment -----------------------------------------------
    def _assign_openings(self, openings: list[Opening], entrances: list[Opening], label_image: np.ndarray, exterior: np.ndarray, spaces: list[Space]) -> list[Opening]:
        by_id = {s.id: s for s in spaces}
        kept: list[Opening] = []
        for opening in openings:
            sides = [self._side_space(opening, sign, label_image, exterior) for sign in (1, -1)]
            a, b = sides
            if a == b:
                continue  # does not separate anything: text, furniture or a symbol inside a room
            if a == "exterior" or b == "exterior":
                inner = b if a == "exterior" else a
                if inner is None:
                    continue
                if not ({"swing", "ml"} & set(opening.sources)):
                    # a door-sized gap in the exterior wall with no door drawn in it is a window
                    self.glass.append(WallElement(polygon=opening.polygon, kind="window", confidence=0.5))
                    continue
                opening.kind = "entrance"
                opening.space_ids = (inner, None)
            elif a is None or b is None:
                continue
            else:
                opening.space_ids = (a, b)
                opening.kind = "passage" if False else "door"
            kept.append(opening)
            for side in opening.space_ids:
                if side and side in by_id:
                    by_id[side].opening_ids.append(opening.id)

        for entrance in entrances:
            near = any(Point(entrance.center).distance(Point(o.center)) < max(entrance.width_px, o.width_px) for o in kept if o.kind == "entrance")
            if near:
                continue
            kept.append(entrance)
            inner = entrance.space_ids[0]
            if inner in by_id:
                by_id[inner].opening_ids.append(entrance.id)
        return kept

    def _side_space(self, opening: Opening, sign: int, label_image: np.ndarray, exterior: np.ndarray) -> str | None:
        depth = max(2.0, opening.polygon.area / max(opening.width_px, 1.0))
        nx, ny = opening.normal
        for offset in (depth / 2 + 2, depth / 2 + self.scale.px(0.15), depth / 2 + self.scale.px(0.35), depth / 2 + self.scale.px(0.6)):
            x = int(round(opening.center[0] + sign * nx * offset))
            y = int(round(opening.center[1] + sign * ny * offset))
            if not (0 <= y < label_image.shape[0] and 0 <= x < label_image.shape[1]):
                return "exterior"
            if exterior[y, x]:
                return "exterior"
            label = int(label_image[y, x])
            if label:
                return f"s{label}"
        return None

    # ---- semantics ----------------------------------------------------------------------
    def _label(self, spaces: list[Space], labels: list[TextLabel]) -> None:
        for label in labels:
            point = Point(label.position)
            for space in spaces:
                if space.polygon.contains(point):
                    space.label = f"{space.label} {label.text}".strip() if space.label else label.text
                    break

    def _classify(self, spaces: list[Space], openings: list[Opening]) -> None:
        by_id = {o.id: o for o in openings}
        best_doors = max((len(s.opening_ids) for s in spaces), default=0)
        for space in spaces:
            doors = [by_id[i] for i in space.opening_ids if i in by_id]
            door_count = len(doors)
            has_entrance = any(o.kind == "entrance" for o in doors)
            text = space.label or ""
            if space.kind == "void" or VOID_WORDS.search(text):
                space.kind = "void"
                continue
            for kind, pattern in VERTICAL_WORDS.items():
                if pattern.search(text):
                    space.kind = "vertical"
                    space.connector_kind = kind  # type: ignore[assignment]
                    break
            if space.kind == "vertical":
                continue
            score = 0.0
            if CIRCULATION_WORDS.search(text):
                score += 2.0
            if door_count >= 3:
                score += 1.5
            if door_count == best_doors and door_count >= 2:
                score += 0.5
            if space.elongation >= 2.5 and space.narrowness <= 0.3:
                score += 1.0
            if has_entrance and door_count >= 2:
                score += 1.0
            if score >= 1.5:
                space.kind = "circulation"
                space.confidence = min(1.0, 0.5 + score / 4)
            else:
                space.kind = "room"
                space.confidence = 0.7 if door_count else 0.4
        if spaces and not any(s.kind == "circulation" for s in spaces):
            candidate = max((s for s in spaces if s.kind == "room"), key=lambda s: (len(s.opening_ids), s.area_px), default=None)
            if candidate is not None and candidate.opening_ids:
                candidate.kind = "circulation"
                candidate.confidence = 0.4
        for opening in openings:
            a, b = opening.space_ids
            kinds = {by_space.kind for by_space in spaces if by_space.id in (a, b)}
            if opening.kind == "door" and kinds == {"circulation"}:
                opening.kind = "passage"
