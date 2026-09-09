"""Minimal planar geometry shared by bounded contexts (no framework dependencies)."""
from __future__ import annotations


def _cross(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def segments_properly_cross(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float, dx: float, dy: float
) -> bool:
    """True only when segment AB passes from one side of CD to the other.

    Endpoint touches and collinear overlap are intentionally ignored so a route can end
    at a doorway or follow a boundary without counting as a through-wall traversal.
    """
    c1 = _cross(ax, ay, bx, by, cx, cy)
    c2 = _cross(ax, ay, bx, by, dx, dy)
    c3 = _cross(cx, cy, dx, dy, ax, ay)
    c4 = _cross(cx, cy, dx, dy, bx, by)
    epsilon = 1e-7
    return (c1 * c2 < -epsilon) and (c3 * c4 < -epsilon)
