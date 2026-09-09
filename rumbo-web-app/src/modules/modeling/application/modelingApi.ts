import { api } from '../../../shared/api/http'
import type { SpatialModel } from '../domain/model'

export function getSpatialModel(floorplanId: string) {
  return api<SpatialModel>(`/api/v1/modeling/${floorplanId}`)
}

export function saveSpatialModel(model: SpatialModel) {
  return api<SpatialModel>(`/api/v1/modeling/${model.floorplan_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pixels_per_meter: model.pixels_per_meter,
      walls: model.walls,
      nodes: model.nodes,
      pois: model.pois,
    }),
  })
}
