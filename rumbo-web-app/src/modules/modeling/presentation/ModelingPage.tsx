import { useEffect, useMemo, useState } from 'react'
import { CircleDot, GitBranch, HelpCircle, MapPin, QrCode, Ruler, Save } from 'lucide-react'
import { PageHeader } from '../../../shared/components/PageHeader'
import { listFloorplans } from '../../floorplans/application/floorplanApi'
import type { Floorplan } from '../../floorplans/domain/floorplan'
import { getNavigationConfig, saveNavigationConfig } from '../../navigation/application/navigationApi'
import type { NavigationConfig } from '../../navigation/domain/navigation'
import { getPositioningConfig, savePositioningConfig } from '../../positioning/application/positioningApi'
import type { PositioningConfig } from '../../positioning/domain/positioning'
import { getSpatialModel, saveSpatialModel } from '../application/modelingApi'
import type { SpatialModel } from '../domain/model'
import { ModelingCanvas } from './components/ModelingCanvas'
import { ModelingTutorial } from './components/ModelingTutorial'

const emptyModel = (floorplanId: string): SpatialModel => ({
  floorplan_id: floorplanId,
  pixels_per_meter: null,
  walls: [],
  nodes: [],
  pois: [],
})
const emptyNavigation = (floorplanId: string): NavigationConfig => ({
  floorplan_id: floorplanId,
  edges: [],
  vertical_connectors: [],
})
const emptyPositioning = (floorplanId: string): PositioningConfig => ({
  floorplan_id: floorplanId,
  qr_anchors: [],
})

export function ModelingPage() {
  const [floorplans, setFloorplans] = useState<Floorplan[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [model, setModel] = useState<SpatialModel | null>(null)
  const [navigation, setNavigation] = useState<NavigationConfig | null>(null)
  const [positioning, setPositioning] = useState<PositioningConfig | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(false)
  const [tutorialOpen, setTutorialOpen] = useState(false)

  useEffect(() => {
    listFloorplans().then((items) => {
      setFloorplans(items)
      if (items[0]) setSelectedId(items[0].id)
    }).catch((e) => setStatus(e instanceof Error ? e.message : 'No se pudieron cargar los planos.'))
  }, [])

  useEffect(() => {
    if (!selectedId) {
      setModel(null)
      setNavigation(null)
      setPositioning(null)
      return
    }
    setLoading(true)
    Promise.all([
      getSpatialModel(selectedId).catch(() => emptyModel(selectedId)),
      getNavigationConfig(selectedId).catch(() => emptyNavigation(selectedId)),
      getPositioningConfig(selectedId).catch(() => emptyPositioning(selectedId)),
    ]).then(([spatial, nav, pos]) => {
      setModel(spatial)
      setNavigation(nav)
      setPositioning(pos)
    }).catch((e) => setStatus(e instanceof Error ? e.message : 'No se pudo cargar el modelo.'))
      .finally(() => setLoading(false))
  }, [selectedId])

  const floorplan = useMemo(
    () => floorplans.find((item) => item.id === selectedId) ?? null,
    [floorplans, selectedId],
  )

  useEffect(() => {
    if (!floorplan || localStorage.getItem('rumbo:modeling-tour-seen')) return
    const timer = window.setTimeout(() => setTutorialOpen(true), 450)
    return () => window.clearTimeout(timer)
  }, [floorplan?.id])

  const save = async () => {
    if (!model || !navigation || !positioning) return
    setSaving(true)
    try {
      const savedModel = await saveSpatialModel(model)
      const [savedNavigation, savedPositioning] = await Promise.all([
        saveNavigationConfig(navigation),
        savePositioningConfig(positioning),
      ])
      setModel(savedModel)
      setNavigation(savedNavigation)
      setPositioning(savedPositioning)
      setStatus('Modelo, navegación y puntos QR guardados.')
      setTimeout(() => setStatus(null), 2200)
    } catch (e) {
      setStatus(e instanceof Error ? e.message : 'No se pudo guardar la configuración.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page modeling-page">
      <PageHeader
        eyebrow="Mapa indoor"
        title="Modelado"
        description="Convierte el plano en un mapa indoor navegable: calibra, define nodos y puntos de atención, conecta recorridos entre pisos y asocia puntos QR."
        actions={
          <>
            <button className="button" onClick={() => setTutorialOpen(true)}><HelpCircle size={16}/> Ver tutorial</button>
            <button className="button primary" onClick={() => void save()} disabled={!model || !navigation || !positioning || saving}>
              <Save size={16} /> {saving ? 'Guardando…' : 'Guardar configuración'}
            </button>
          </>
        }
      />

      <div className="model-summary-bar">
        <label>
          <span>Plano activo</span>
          <select data-tour="floorplan" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
            {floorplans.length === 0 && <option value="">No hay planos</option>}
            {floorplans.map((item) => (
              <option value={item.id} key={item.id}>{item.building_name} · {item.floor_label}</option>
            ))}
          </select>
        </label>
        <Metric icon={<Ruler size={15} />} label="Escala" value={model?.pixels_per_meter ? `${model.pixels_per_meter.toFixed(1)} px/m` : 'Pendiente'} />
        <Metric icon={<CircleDot size={15} />} label="Nodos" value={String(model?.nodes.length ?? 0)} />
        <Metric icon={<MapPin size={15} />} label="Puntos" value={String(model?.pois.length ?? 0)} />
        <Metric icon={<GitBranch size={15} />} label="Conexiones" value={String((navigation?.edges.length ?? 0) + (navigation?.vertical_connectors.length ?? 0))} />
        <Metric icon={<QrCode size={15} />} label="QR" value={String(positioning?.qr_anchors.length ?? 0)} />
      </div>

      {status && <div className="toast">{status}</div>}

      {!floorplan || !model || !navigation || !positioning || loading ? (
        <div className="panel empty-model">
          <strong>{loading ? 'Cargando configuración…' : 'No hay una fuente para modelar.'}</strong>
          {!loading && <span>Sube un plano desde Planos.</span>}
        </div>
      ) : (
        <ModelingCanvas
          floorplan={floorplan}
          floorplans={floorplans}
          model={model}
          navigation={navigation}
          positioning={positioning}
          onModelChange={setModel}
          onNavigationChange={setNavigation}
          onPositioningChange={setPositioning}
        />
      )}
      <ModelingTutorial open={tutorialOpen} onClose={() => setTutorialOpen(false)} />
    </div>
  )
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="metric-chip">{icon}<span>{label}</span><strong>{value}</strong></div>
}
