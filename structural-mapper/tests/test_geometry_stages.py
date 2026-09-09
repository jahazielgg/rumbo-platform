import numpy as np
from shapely.geometry import Polygon

from mapper.contracts import Scale, StructuralMasks
from mapper.geometry import line_closing, mask_to_polygons, rasterize
from mapper.graph.skeleton import prune_spurs, skeleton_graph
from mapper.reconstruction.openings import detect_openings
from mapper.reconstruction.polygons import reconstruct_walls


def _two_rooms_with_door(door_px: int = 24, wall_px: int = 8, size: int = 300) -> np.ndarray:
    """Two rooms side by side, separated by a wall with one doorway."""
    wall = np.zeros((size, size), dtype=bool)
    wall[:wall_px, :] = wall[-wall_px:, :] = True
    wall[:, :wall_px] = wall[:, -wall_px:] = True
    mid = size // 2
    wall[:, mid - wall_px // 2 : mid + wall_px // 2] = True
    wall[size // 2 - door_px // 2 : size // 2 + door_px // 2, mid - wall_px // 2 : mid + wall_px // 2] = False
    return wall


def test_line_closing_bridges_gaps_in_thin_walls_but_not_at_image_border():
    wall = np.zeros((120, 200), dtype=bool)
    wall[60:66, 20:90] = True
    wall[60:66, 110:180] = True  # 20 px gap
    closed = line_closing(wall, 40)
    assert closed[63, 100]  # gap sealed
    assert not closed[5, 100]  # margins stay free
    assert not closed[63, 5]


def test_wall_reconstruction_and_gap_door_detection():
    scale = Scale(20.0, "calibrated")
    wall = _two_rooms_with_door()
    empty = np.zeros_like(wall)
    masks = StructuralMasks(wall=wall, door=empty, window=empty.copy())
    walls = reconstruct_walls(masks, scale)
    assert sum(w.kind == "wall" for w in walls) >= 1
    openings = detect_openings(masks, walls, scale, wall.shape)
    assert len(openings) == 1
    opening = openings[0]
    assert abs(opening.center[0] - 150) < 6 and abs(opening.center[1] - 150) < 6
    assert 20 <= opening.width_px <= 30
    assert abs(abs(opening.normal[0]) - 1.0) < 0.05  # the wall is vertical, the normal horizontal


def test_gap_detection_ignores_concave_corners_and_facing_walls():
    scale = Scale(20.0, "calibrated")
    wall = np.zeros((300, 300), dtype=bool)
    wall[:8, :] = wall[-8:, :] = True
    wall[:, :8] = wall[:, -8:] = True
    # an L-shaped partition (concave corner) and a corridor formed by two parallel stubs
    wall[100:108, 0:160] = True
    wall[100:200, 152:160] = True
    wall[220:228, 0:120] = True
    wall[250:258, 0:120] = True  # 22 px corridor between two parallel walls
    empty = np.zeros_like(wall)
    masks = StructuralMasks(wall=wall, door=empty, window=empty.copy())
    walls = reconstruct_walls(masks, scale)
    assert detect_openings(masks, walls, scale, wall.shape) == []


def test_mask_to_polygons_keeps_holes_and_rasterize_round_trips():
    mask = np.zeros((100, 100), dtype=bool)
    mask[10:90, 10:90] = True
    mask[40:60, 40:60] = False
    polygons = mask_to_polygons(mask, simplify_px=1.0)
    assert len(polygons) == 1 and len(polygons[0].interiors) == 1
    back = rasterize(polygons, mask.shape)
    assert (back ^ mask).mean() < 0.02


def test_skeleton_graph_of_t_shape_has_one_junction_and_prunes_short_spurs():
    mask = np.zeros((200, 200), dtype=bool)
    mask[95:105, 20:180] = True
    mask[20:105, 95:105] = True
    graph = skeleton_graph(mask)
    junctions = [n for n in graph.nodes if graph.degree(n) >= 3]
    assert len(junctions) == 1
    prune_spurs(graph, min_length=200, protected=set(junctions))
    assert graph.number_of_edges() <= 1
