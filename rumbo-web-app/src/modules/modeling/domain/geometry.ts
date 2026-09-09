import type { Point2D, WallSegment } from './model'

const cross = (a: Point2D, b: Point2D, c: Point2D) =>
  (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)

/**
 * True only when two segments properly cross each other. Endpoint touches and
 * collinear overlap are intentionally allowed so a route can terminate at a doorway
 * or follow a boundary without being treated as a through-wall traversal.
 */
export function segmentsProperlyCross(a: Point2D, b: Point2D, c: Point2D, d: Point2D): boolean {
  const c1 = cross(a, b, c)
  const c2 = cross(a, b, d)
  const c3 = cross(c, d, a)
  const c4 = cross(c, d, b)
  const epsilon = 1e-7
  return c1 * c2 < -epsilon && c3 * c4 < -epsilon
}

export function segmentCrossesWalls(a: Point2D, b: Point2D, walls: WallSegment[]): boolean {
  return walls.some((wall) => segmentsProperlyCross(a, b, wall.start, wall.end))
}

export function clampPoint(point: Point2D, width: number, height: number): Point2D {
  return {
    x: Math.max(0, Math.min(width, point.x)),
    y: Math.max(0, Math.min(height, point.y)),
  }
}
