import { useMemo, useState } from 'react'
import { assetUrl } from '../../../../shared/api/http'
import type { Floorplan } from '../../../floorplans/domain/floorplan'
import type { SpatialModel } from '../../../modeling/domain/model'
import type { NavigationConfig, RouteResult } from '../../domain/navigation'

export function NavigationMap({ floorplan, model, navigation, route }: { floorplan: Floorplan; model: SpatialModel; navigation: NavigationConfig; route: RouteResult | null }) {
  const [size, setSize] = useState({ width: 1000, height: 700 })
  const nodeById = useMemo(() => new Map(model.nodes.map((node) => [node.id, node])), [model.nodes])
  const routeNodeIds = useMemo(() => new Set(route?.nodes.filter((node) => node.floorplan_id === floorplan.id).map((node) => node.node_id) ?? []), [route, floorplan.id])
  const routeLinks = useMemo(() => route?.links.filter((link) => link.from_floorplan_id === floorplan.id && link.to_floorplan_id === floorplan.id) ?? [], [route, floorplan.id])
  return <div className="navigation-canvas-stage"><div className="plan-frame navigation-plan-frame"><img src={assetUrl(floorplan.preview_url || floorplan.file_url)} alt={floorplan.name} draggable={false} onLoad={(event) => setSize({ width: event.currentTarget.naturalWidth || 1000, height: event.currentTarget.naturalHeight || 700 })}/><svg className="navigation-layer" viewBox={`0 0 ${size.width} ${size.height}`} preserveAspectRatio="none">{navigation.edges.map((edge) => { const from = nodeById.get(edge.from_node_id); const to = nodeById.get(edge.to_node_id); if (!from || !to) return null; return <line key={edge.id} x1={from.position.x} y1={from.position.y} x2={to.position.x} y2={to.position.y} className="navigation-base-edge" /> })}{routeLinks.map((link, index) => { const from = nodeById.get(link.from_node_id); const to = nodeById.get(link.to_node_id); if (!from || !to) return null; return <line key={`${link.from_node_id}-${link.to_node_id}-${index}`} x1={from.position.x} y1={from.position.y} x2={to.position.x} y2={to.position.y} className="navigation-route-edge" /> })}{model.nodes.map((node) => { const onRoute = routeNodeIds.has(node.id); return <g key={node.id} className={`navigation-node ${onRoute ? 'on-route' : ''}`} transform={`translate(${node.position.x} ${node.position.y})`}><circle r={onRoute ? 7 : 4} />{onRoute && <text className="navigation-node-label" x="11" y="4">{node.label}</text>}</g> })}</svg></div></div>
}
