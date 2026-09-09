import { api } from '../../../shared/api/http'
import type { NavigationConfig, RouteRequest, RouteResult } from '../domain/navigation'

export function getNavigationConfig(floorplanId: string) {
  return api<NavigationConfig>(`/api/v1/navigation/${floorplanId}`)
}

export function saveNavigationConfig(config: NavigationConfig) {
  return api<NavigationConfig>(`/api/v1/navigation/${config.floorplan_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ edges: config.edges, vertical_connectors: config.vertical_connectors }),
  })
}

export function calculateRoute(request: RouteRequest) {
  return api<RouteResult>('/api/v1/navigation/route', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
}
