import { useEffect, useMemo, useState } from 'react'
import { Accessibility, ArrowRight, LocateFixed, MapPinned, Navigation2, Route, ScanLine } from 'lucide-react'
import { PageHeader } from '../../../shared/components/PageHeader'
import { listFloorplans } from '../../floorplans/application/floorplanApi'
import type { Floorplan } from '../../floorplans/domain/floorplan'
import { getSpatialModel } from '../../modeling/application/modelingApi'
import type { SpatialModel } from '../../modeling/domain/model'
import { getPositioningConfig } from '../../positioning/application/positioningApi'
import type { PositioningConfig } from '../../positioning/domain/positioning'
import { calculateRoute, getNavigationConfig } from '../application/navigationApi'
import type { NavigationConfig, RouteResult } from '../domain/navigation'
import { NavigationMap } from './components/NavigationMap'

type FloorData = { floorplan: Floorplan; model: SpatialModel; navigation: NavigationConfig; positioning: PositioningConfig }
type LocationOption = { value: string; floorplanId: string; nodeId: string; label: string; detail: string }
function splitLocation(value: string) { const [floorplanId, nodeId] = value.split('::'); return { floorplanId, nodeId } }

export function NavigationPage() {
  const [floors, setFloors] = useState<FloorData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [accessibleOnly, setAccessibleOnly] = useState(false)
  const [route, setRoute] = useState<RouteResult | null>(null)
  const [activeFloorId, setActiveFloorId] = useState('')
  const [calculating, setCalculating] = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const floorplans = await listFloorplans()
        const loaded = await Promise.all(floorplans.map(async (floorplan) => {
          const [model, navigation, positioning] = await Promise.all([getSpatialModel(floorplan.id), getNavigationConfig(floorplan.id), getPositioningConfig(floorplan.id)])
          return { floorplan, model, navigation, positioning }
        }))
        setFloors(loaded); setError(null)
      } catch (e) { setError(e instanceof Error ? e.message : 'No se pudo cargar el mapa de navegación.') }
      finally { setLoading(false) }
    }
    void load()
  }, [])

  // Internal skeleton vertices are implementation details. The user chooses a named,
  // physically meaningful place: QR anchor, POI or explicit entrance.
  const originOptions = useMemo<LocationOption[]>(() => {
    const result: LocationOption[] = []
    for (const floor of floors) {
      const nodeById = new Map(floor.model.nodes.map((node) => [node.id, node]))
      const usedLabels = new Set<string>()
      const add = (nodeId: string, label: string, suffix: string) => {
        const node = nodeById.get(nodeId)
        if (!node) return
        const key = `${node.id}::${label}`
        if (usedLabels.has(key)) return
        usedLabels.add(key)
        result.push({
          value: `${floor.floorplan.id}::${node.id}`,
          floorplanId: floor.floorplan.id,
          nodeId: node.id,
          label,
          detail: `${floor.floorplan.building_name} · ${floor.floorplan.floor_label} · ${suffix}`,
        })
      }
      for (const qr of floor.positioning.qr_anchors) add(qr.node_id, qr.label, 'QR')
      for (const poi of floor.model.pois) add(poi.node_id, poi.name, 'punto')
      for (const node of floor.model.nodes.filter((item) => item.kind === 'entrance')) add(node.id, node.label, 'entrada')
    }
    return result
  }, [floors])

  const destinationOptions = useMemo<LocationOption[]>(() => floors.flatMap((floor) => floor.model.pois.map((poi) => ({ value: `${floor.floorplan.id}::${poi.node_id}`, floorplanId: floor.floorplan.id, nodeId: poi.node_id, label: poi.name, detail: `${floor.floorplan.building_name} · ${floor.floorplan.floor_label}` }))), [floors])

  useEffect(() => {
    if (!origin && originOptions[0]) setOrigin(originOptions[0].value)
    if (!destination && destinationOptions[0]) setDestination((destinationOptions.find((item) => item.value !== originOptions[0]?.value) ?? destinationOptions[0]).value)
  }, [origin, destination, originOptions, destinationOptions])

  const routeFloorIds = useMemo(() => Array.from(new Set(route?.nodes.map((node) => node.floorplan_id) ?? [])), [route])
  const activeFloor = floors.find((item) => item.floorplan.id === activeFloorId) ?? floors.find((item) => item.floorplan.id === routeFloorIds[0]) ?? floors[0]

  const buildRoute = async () => {
    if (!origin || !destination) return
    const start = splitLocation(origin); const end = splitLocation(destination)
    setCalculating(true); setError(null)
    try {
      const result = await calculateRoute({ start_floorplan_id: start.floorplanId, start_node_id: start.nodeId, destination_floorplan_id: end.floorplanId, destination_node_id: end.nodeId, accessible_only: accessibleOnly })
      setRoute(result); setActiveFloorId(result.nodes[0]?.floorplan_id ?? start.floorplanId)
    } catch (e) { setRoute(null); setError(e instanceof Error ? e.message : 'No se pudo calcular la ruta.') }
    finally { setCalculating(false) }
  }

  const selectedDestination = destinationOptions.find((item) => item.value === destination)
  const instructions = useMemo(() => makeInstructions(route, floors, selectedDestination?.label), [route, floors, selectedDestination?.label])

  return (
    <div className="page navigation-page" data-tour="navigation">
      <PageHeader eyebrow="Routing" title="Navegación" description="Simula el recorrido que verá el usuario final. Rumbo calcula el camino usando el grafo configurado en Modelado." />
      {error && <div className="alert error">{error}</div>}
      <section className="navigation-controls panel">
        <label className="navigation-field"><span><LocateFixed size={14}/> Origen</span><select value={origin} onChange={(event) => { setOrigin(event.target.value); setRoute(null) }}>{originOptions.map((item, index) => <option key={`${item.value}-${item.label}-${index}`} value={item.value}>{item.label} · {item.detail}</option>)}</select></label>
        <ArrowRight className="navigation-arrow" size={18} />
        <label className="navigation-field"><span><MapPinned size={14}/> Destino</span><select value={destination} onChange={(event) => { setDestination(event.target.value); setRoute(null) }}>{destinationOptions.map((item) => <option key={`${item.value}-${item.label}`} value={item.value}>{item.label} · {item.detail}</option>)}</select></label>
        <label className="accessible-toggle"><input type="checkbox" checked={accessibleOnly} onChange={(event) => { setAccessibleOnly(event.target.checked); setRoute(null) }} /><Accessibility size={16}/><span>Solo accesible</span></label>
        <button className="button primary" onClick={() => void buildRoute()} disabled={!origin || !destination || calculating || loading}><Route size={16}/> {calculating ? 'Calculando…' : 'Calcular ruta'}</button>
      </section>
      {loading ? <div className="panel navigation-empty">Cargando red de navegación…</div> : floors.length === 0 ? <div className="panel navigation-empty">Primero configura un plano desde Modelado.</div> : (
        <div className="navigation-layout">
          <section className="panel navigation-map-panel">
            <div className="navigation-map-heading"><div><span className="panel-kicker">Vista de ruta</span><strong>{activeFloor?.floorplan.building_name} · {activeFloor?.floorplan.floor_label}</strong></div>{routeFloorIds.length > 1 && <div className="floor-tabs">{routeFloorIds.map((id) => { const floor = floors.find((item) => item.floorplan.id === id); return <button key={id} className={activeFloor?.floorplan.id === id ? 'active' : ''} onClick={() => setActiveFloorId(id)}>{floor?.floorplan.floor_label ?? 'Piso'}</button> })}</div>}</div>
            {activeFloor && <NavigationMap floorplan={activeFloor.floorplan} model={activeFloor.model} navigation={activeFloor.navigation} route={route} />}
          </section>
          <aside className="panel route-summary">{!route ? <div className="route-placeholder"><Navigation2 size={30}/><strong>Prueba una ruta</strong><p>Selecciona un QR, punto o entrada como origen y un punto de atención como destino.</p></div> : <><div className="route-hero"><span>Distancia estimada</span><strong>{route.total_distance_meters.toFixed(1)} m</strong><small>{route.nodes.length} tramos internos · {routeFloorIds.length} {routeFloorIds.length === 1 ? 'piso' : 'pisos'}</small></div><div className="route-instructions">{instructions.map((instruction, index) => <div className="route-instruction" key={`${instruction}-${index}`}><span>{index + 1}</span><p>{instruction}</p></div>)}</div><div className="route-qr-note"><ScanLine size={16}/><span>En la app móvil, un QR puede establecer el origen real antes de iniciar esta ruta.</span></div></>}</aside>
        </div>
      )}
    </div>
  )
}

function makeInstructions(route: RouteResult | null, floors: FloorData[], destinationName?: string) {
  if (!route || route.nodes.length === 0) return []
  const floorName = (id: string) => floors.find((item) => item.floorplan.id === id)?.floorplan.floor_label ?? 'otro piso'
  const result: string[] = []; let corridorDistance = 0
  const flushCorridor = (targetLabel?: string) => { if (corridorDistance <= 0) return; result.push(`Avanza ${corridorDistance.toFixed(1)} m${targetLabel ? ` hasta ${targetLabel}` : ''}.`); corridorDistance = 0 }
  route.links.forEach((link, index) => { const targetNode = route.nodes[index + 1]; if (link.kind === 'corridor' || link.kind === 'doorway') { corridorDistance += link.distance_meters; const next = route.links[index + 1]; if (!next || (next.kind !== 'corridor' && next.kind !== 'doorway')) flushCorridor(targetNode?.label); return } flushCorridor(); const action = link.kind === 'elevator' ? 'Toma el ascensor' : link.kind === 'stairs' ? 'Usa las escaleras' : 'Usa la rampa'; result.push(`${action}${link.label ? ` (${link.label})` : ''} hacia ${floorName(link.to_floorplan_id)}.`) })
  flushCorridor(); result.push(`Llegaste a ${destinationName ?? route.nodes.at(-1)?.label ?? 'tu destino'}.`); return result
}
