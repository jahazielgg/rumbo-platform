export type EdgeKind = 'corridor' | 'doorway'
export type ConnectorKind = 'elevator' | 'stairs' | 'ramp'

export interface NavigationEdge { id: string; from_node_id: string; to_node_id: string; kind: EdgeKind; accessible: boolean }
export interface VerticalConnector { id: string; kind: ConnectorKind; label: string; source_node_id: string; target_floorplan_id: string; target_node_id: string; accessible: boolean; bidirectional: boolean }
export interface NavigationConfig { floorplan_id: string; edges: NavigationEdge[]; vertical_connectors: VerticalConnector[] }
export interface RouteRequest { start_floorplan_id: string; start_node_id: string; destination_floorplan_id: string; destination_node_id: string; accessible_only: boolean }
export interface RouteNode { floorplan_id: string; node_id: string; label: string; x: number; y: number }
export interface RouteLink { from_floorplan_id: string; from_node_id: string; to_floorplan_id: string; to_node_id: string; distance_meters: number; kind: string; label: string | null; accessible: boolean }
export interface RouteResult { total_distance_meters: number; nodes: RouteNode[]; links: RouteLink[] }
