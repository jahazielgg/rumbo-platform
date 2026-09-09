import { api } from '../../../shared/api/http'
import type { PositioningConfig } from '../domain/positioning'

export function getPositioningConfig(floorplanId: string) {
  return api<PositioningConfig>(`/api/v1/positioning/${floorplanId}`)
}

export function savePositioningConfig(config: PositioningConfig) {
  return api<PositioningConfig>(`/api/v1/positioning/${config.floorplan_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ qr_anchors: config.qr_anchors }),
  })
}
