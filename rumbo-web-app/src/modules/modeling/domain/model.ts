export interface Point2D { x: number; y: number }
export interface WallSegment { id: string; start: Point2D; end: Point2D }
export type NodeKind = 'waypoint' | 'entrance' | 'decision' | 'door' | 'room' | 'connector'
export interface MapNode { id: string; position: Point2D; label: string; kind: NodeKind }
export interface PointOfInterest { id: string; name: string; category: string; position: Point2D; node_id: string }

export interface SpatialModel {
  floorplan_id: string
  pixels_per_meter: number | null
  walls: WallSegment[]
  nodes: MapNode[]
  pois: PointOfInterest[]
}

export type Tool = 'select' | 'wall' | 'measure' | 'scale' | 'node' | 'poi' | 'edge' | 'connector' | 'qr'
