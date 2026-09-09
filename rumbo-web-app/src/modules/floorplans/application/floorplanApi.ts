import { api } from '../../../shared/api/http'
import type { Floorplan } from '../domain/floorplan'

export function listFloorplans() {
  return api<Floorplan[]>('/api/v1/floorplans')
}

export function uploadFloorplan(data: FormData) {
  return api<Floorplan>('/api/v1/floorplans', { method: 'POST', body: data })
}

export function deleteFloorplan(id: string) {
  return api<void>(`/api/v1/floorplans/${id}`, { method: 'DELETE' })
}
