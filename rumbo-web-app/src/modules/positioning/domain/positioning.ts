export interface QRAnchor {
  id: string
  code: string
  label: string
  node_id: string
}

export interface PositioningConfig {
  floorplan_id: string
  qr_anchors: QRAnchor[]
}
