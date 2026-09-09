import { useEffect, useMemo, useState } from 'react'
import { ArrowUpDown, Blocks, Check, CircleDot, GitBranch, MapPin, MousePointer2, QrCode, Ruler, Scaling, Sparkles, Trash2, Undo2 } from 'lucide-react'
import { assetUrl } from '../../../../shared/api/http'
import type { Floorplan } from '../../../floorplans/domain/floorplan'
import type { ConnectorKind, NavigationConfig, NavigationEdge } from '../../../navigation/domain/navigation'
import type { PositioningConfig } from '../../../positioning/domain/positioning'
import { generateAutomaticModel, summarizeProposal } from '../../application/autoModel'
import type { ValidationIssue } from '../../application/autoModel'
import { getSpatialModel } from '../../application/modelingApi'
import { clampPoint, segmentCrossesWalls } from '../../domain/geometry'
import type { MapNode, Point2D, PointOfInterest, SpatialModel, Tool, WallSegment } from '../../domain/model'

const uid = () => crypto.randomUUID()
const dist = (a: Point2D, b: Point2D) => Math.hypot(b.x - a.x, b.y - a.y)

type Selection = { kind: 'node' | 'wall' | 'poi' | 'edge'; id: string } | null
type DragTarget = { kind: 'node' | 'poi' | 'wall-start' | 'wall-end'; id: string } | null

export function ModelingCanvas({ floorplan, floorplans, model, navigation, positioning, onModelChange, onNavigationChange, onPositioningChange }: {
  floorplan: Floorplan
  floorplans: Floorplan[]
  model: SpatialModel
  navigation: NavigationConfig
  positioning: PositioningConfig
  onModelChange: (value: SpatialModel) => void
  onNavigationChange: (value: NavigationConfig) => void
  onPositioningChange: (value: PositioningConfig) => void
}) {
  const [tool, setTool] = useState<Tool>('select')
  const [draft, setDraft] = useState<Point2D | null>(null)
  const [measure, setMeasure] = useState<[Point2D, Point2D] | null>(null)
  const [scaleDraft, setScaleDraft] = useState<[Point2D, Point2D] | null>(null)
  const [meters, setMeters] = useState('')
  const [size, setSize] = useState({ width: 1000, height: 700 })
  const [edgeStart, setEdgeStart] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [selection, setSelection] = useState<Selection>(null)
  const [drag, setDrag] = useState<DragTarget>(null)
  const [autoGenerating, setAutoGenerating] = useState(false)
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([])
  const [poiDraft, setPoiDraft] = useState<{ point: Point2D; nodeId: string } | null>(null)
  const [poiName, setPoiName] = useState('')
  const [poiCategory, setPoiCategory] = useState('atencion')
  const [connectorSource, setConnectorSource] = useState<string | null>(null)
  const [connectorKind, setConnectorKind] = useState<ConnectorKind>('elevator')
  const [connectorLabel, setConnectorLabel] = useState('Ascensor')
  const [targetFloorId, setTargetFloorId] = useState('')
  const [targetNodeId, setTargetNodeId] = useState('')
  const [targetNodes, setTargetNodes] = useState<MapNode[]>([])
  const [qrNode, setQrNode] = useState<string | null>(null)
  const [qrLabel, setQrLabel] = useState('')
  const [qrCode, setQrCode] = useState('')

  const source = assetUrl(floorplan.preview_url || floorplan.file_url)
  const nodes = useMemo(() => new Map(model.nodes.map((node) => [node.id, node])), [model.nodes])
  const siblingFloors = floorplans.filter((item) => item.building_name === floorplan.building_name && item.id !== floorplan.id)

  const selectedNode = selection?.kind === 'node' ? model.nodes.find((item) => item.id === selection.id) ?? null : null
  const selectedWall = selection?.kind === 'wall' ? model.walls.find((item) => item.id === selection.id) ?? null : null
  const selectedPoi = selection?.kind === 'poi' ? model.pois.find((item) => item.id === selection.id) ?? null : null
  const selectedEdge = selection?.kind === 'edge' ? navigation.edges.find((item) => item.id === selection.id) ?? null : null

  const cancelTransient = () => {
    setDraft(null); setMeasure(null); setScaleDraft(null); setEdgeStart(null); setPoiDraft(null); setConnectorSource(null); setQrNode(null); setDrag(null); setNotice(null)
  }

  const chooseTool = (next: Tool) => {
    cancelTransient()
    setSelection(null)
    setTool(next)
  }

  useEffect(() => {
    cancelTransient()
    setSelection(null)
  }, [floorplan.id])

  useEffect(() => {
    if (!targetFloorId) { setTargetNodes([]); setTargetNodeId(''); return }
    getSpatialModel(targetFloorId).then((value) => {
      setTargetNodes(value.nodes)
      setTargetNodeId(value.nodes[0]?.id ?? '')
    }).catch(() => { setTargetNodes([]); setTargetNodeId('') })
  }, [targetFloorId])

  const undoWall = () => {
    if (draft) {
      setDraft(null)
      return
    }
    if (model.walls.length) onModelChange({ ...model, walls: model.walls.slice(0, -1) })
  }

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setDraft(null); setDrag(null); setSelection(null); setEdgeStart(null)
        return
      }
      if (tool === 'wall' && (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault(); undoWall()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [tool, draft, model.walls])

  const pointFromSvg = (svg: SVGSVGElement, clientX: number, clientY: number): Point2D => {
    const rect = svg.getBoundingClientRect()
    return clampPoint({
      x: ((clientX - rect.left) / rect.width) * size.width,
      y: ((clientY - rect.top) / rect.height) * size.height,
    }, size.width, size.height)
  }

  const clickCanvas = (event: React.MouseEvent<SVGSVGElement>) => {
    if (tool === 'select') {
      setSelection(null)
      return
    }
    if (['edge', 'connector', 'qr'].includes(tool)) return
    const point = pointFromSvg(event.currentTarget, event.clientX, event.clientY)
    if (tool === 'node') {
      onModelChange({ ...model, nodes: [...model.nodes, { id: uid(), position: point, label: `N${model.nodes.length + 1}`, kind: 'waypoint' }] })
      return
    }
    if (tool === 'poi') {
      if (!model.nodes.length) { setNotice('Primero crea un nodo transitable.'); return }
      const nearest = model.nodes.reduce((best, node) => dist(node.position, point) < dist(best.position, point) ? node : best)
      setPoiDraft({ point, nodeId: nearest.id }); setPoiName(''); setNotice(null); return
    }
    if (!draft) { setDraft(point); return }
    if (tool === 'wall') {
      onModelChange({ ...model, walls: [...model.walls, { id: uid(), start: draft, end: point }] })
      setDraft(point); return
    }
    if (tool === 'measure') { setMeasure([draft, point]); setDraft(null); return }
    if (tool === 'scale') { setScaleDraft([draft, point]); setDraft(null) }
  }

  const clickNode = (event: React.MouseEvent<SVGGElement>, node: MapNode) => {
    event.stopPropagation(); setNotice(null)
    if (tool === 'select') { setSelection({ kind: 'node', id: node.id }); return }
    if (tool === 'edge') {
      if (!edgeStart) { setEdgeStart(node.id); return }
      if (edgeStart === node.id) { setEdgeStart(null); return }
      const start = nodes.get(edgeStart)
      if (!start) { setEdgeStart(null); return }
      if (segmentCrossesWalls(start.position, node.position, model.walls)) {
        setNotice('Esa conexión atraviesa una pared. Coloca nodos en el pasadizo o en la abertura y conecta por ahí.')
        setEdgeStart(null)
        return
      }
      const duplicate = navigation.edges.some((edge) =>
        (edge.from_node_id === edgeStart && edge.to_node_id === node.id) ||
        (edge.from_node_id === node.id && edge.to_node_id === edgeStart),
      )
      if (!duplicate) onNavigationChange({ ...navigation, edges: [...navigation.edges, { id: uid(), from_node_id: edgeStart, to_node_id: node.id, kind: 'corridor', accessible: true }] })
      else setNotice('Esos nodos ya están conectados.')
      setEdgeStart(null); return
    }
    if (tool === 'connector') {
      setConnectorSource(node.id)
      setTargetFloorId(siblingFloors[0]?.id ?? '')
      return
    }
    if (tool === 'qr') {
      setQrNode(node.id); setQrLabel(`QR ${node.label}`); setQrCode(`rumbo://anchor/${uid()}`)
    }
  }

  const pointerDownNode = (event: React.PointerEvent<SVGGElement>, node: MapNode) => {
    if (tool !== 'select') return
    event.stopPropagation()
    setSelection({ kind: 'node', id: node.id })
    setDrag({ kind: 'node', id: node.id })
  }

  const pointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    if (!drag) return
    const point = pointFromSvg(event.currentTarget, event.clientX, event.clientY)
    if (drag.kind === 'node') {
      onModelChange({ ...model, nodes: model.nodes.map((node) => node.id === drag.id ? { ...node, position: point } : node) })
    } else if (drag.kind === 'poi') {
      onModelChange({ ...model, pois: model.pois.map((poi) => poi.id === drag.id ? { ...poi, position: point } : poi) })
    } else {
      onModelChange({ ...model, walls: model.walls.map((wall) => wall.id === drag.id ? {
        ...wall,
        ...(drag.kind === 'wall-start' ? { start: point } : { end: point }),
      } : wall) })
    }
  }

  const applyScale = () => {
    if (!scaleDraft) return
    const real = Number(meters)
    if (!Number.isFinite(real) || real <= 0) { setNotice('Ingresa una distancia válida en metros.'); return }
    onModelChange({ ...model, pixels_per_meter: dist(scaleDraft[0], scaleDraft[1]) / real })
    setScaleDraft(null); setMeters(''); setNotice('Escala calibrada correctamente.')
  }

  const addPoi = () => {
    if (!poiDraft || !poiName.trim()) return
    onModelChange({ ...model, pois: [...model.pois, { id: uid(), name: poiName.trim(), category: poiCategory, position: poiDraft.point, node_id: poiDraft.nodeId }] })
    setPoiDraft(null); setPoiName('')
  }

  const addConnector = () => {
    if (!connectorSource || !targetFloorId || !targetNodeId || !connectorLabel.trim()) return
    onNavigationChange({ ...navigation, vertical_connectors: [...navigation.vertical_connectors, { id: uid(), kind: connectorKind, label: connectorLabel.trim(), source_node_id: connectorSource, target_floorplan_id: targetFloorId, target_node_id: targetNodeId, accessible: connectorKind !== 'stairs', bidirectional: true }] })
    setConnectorSource(null)
  }

  const addQr = () => {
    if (!qrNode || !qrLabel.trim() || !qrCode.trim()) return
    onPositioningChange({ ...positioning, qr_anchors: [...positioning.qr_anchors, { id: uid(), code: qrCode.trim(), label: qrLabel.trim(), node_id: qrNode }] })
    setQrNode(null); setQrLabel(''); setQrCode('')
  }

  const removeNode = (id: string) => {
    onModelChange({ ...model, nodes: model.nodes.filter((node) => node.id !== id), pois: model.pois.filter((poi) => poi.node_id !== id) })
    onNavigationChange({ ...navigation, edges: navigation.edges.filter((edge) => edge.from_node_id !== id && edge.to_node_id !== id), vertical_connectors: navigation.vertical_connectors.filter((item) => item.source_node_id !== id) })
    onPositioningChange({ ...positioning, qr_anchors: positioning.qr_anchors.filter((item) => item.node_id !== id) })
    setSelection(null)
  }

  const removeWall = (id: string) => { onModelChange({ ...model, walls: model.walls.filter((item) => item.id !== id) }); setSelection(null) }
  const removePoi = (id: string) => { onModelChange({ ...model, pois: model.pois.filter((item) => item.id !== id) }); setSelection(null) }
  const removeEdge = (id: string) => { onNavigationChange({ ...navigation, edges: navigation.edges.filter((item) => item.id !== id) }); setSelection(null) }

  const updateNode = (patch: Partial<MapNode>) => {
    if (!selectedNode) return
    onModelChange({ ...model, nodes: model.nodes.map((item) => item.id === selectedNode.id ? { ...item, ...patch } : item) })
  }
  const updateWall = (patch: Partial<WallSegment>) => {
    if (!selectedWall) return
    onModelChange({ ...model, walls: model.walls.map((item) => item.id === selectedWall.id ? { ...item, ...patch } : item) })
  }
  const updatePoi = (patch: Partial<PointOfInterest>) => {
    if (!selectedPoi) return
    onModelChange({ ...model, pois: model.pois.map((item) => item.id === selectedPoi.id ? { ...item, ...patch } : item) })
  }
  const updateEdge = (patch: Partial<NavigationEdge>) => {
    if (!selectedEdge) return
    onNavigationChange({ ...navigation, edges: navigation.edges.map((item) => item.id === selectedEdge.id ? { ...item, ...patch } : item) })
  }

  const runAutomaticModel = async () => {
    const hasEditableData = model.nodes.length > 0 || model.pois.length > 0 || navigation.edges.length > 0 || navigation.vertical_connectors.length > 0 || positioning.qr_anchors.length > 0
    if (hasEditableData && !window.confirm('La generación automática reemplazará nodos, conexiones, puntos, conectores entre pisos y QR actuales. Las paredes y la calibración se conservarán. ¿Continuar?')) return
    setAutoGenerating(true)
    setNotice('Interpretando paredes, puertas, espacios y circulación del plano…')
    try {
      const result = await generateAutomaticModel(source, model, navigation, size)
      onModelChange(result.model)
      onNavigationChange(result.navigation)
      onPositioningChange({ ...positioning, qr_anchors: [] })
      setTool('select')
      setSelection(null)
      setValidationIssues(result.structural.validation.issues)
      setNotice(summarizeProposal(result))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo generar el modelo automáticamente.')
    } finally {
      setAutoGenerating(false)
    }
  }

  const edgeIsInvalid = (edge: NavigationEdge) => {
    const a = nodes.get(edge.from_node_id)
    const b = nodes.get(edge.to_node_id)
    return Boolean(a && b && segmentCrossesWalls(a.position, b.position, model.walls))
  }

  const measureText = measure ? (model.pixels_per_meter ? `${(dist(measure[0], measure[1]) / model.pixels_per_meter).toFixed(2)} m` : `${dist(measure[0], measure[1]).toFixed(0)} px`) : null

  return <div className="model-workspace">
    <div className="model-toolbar panel">
      <div className="tool-group">
        <span className="tool-group-label">Edición</span>
        <Tool active={tool === 'select'} onClick={() => chooseTool('select')} icon={<MousePointer2 size={16}/>} label="Seleccionar" help="Selecciona, mueve y edita elementos existentes." />
        <Tool tour="wall" active={tool === 'wall'} onClick={() => chooseTool('wall')} icon={<Blocks size={16}/>} label="Pared" help="Representa límites físicos. No es una ruta." />
        <Tool tour="node" active={tool === 'node'} onClick={() => chooseTool('node')} icon={<CircleDot size={16}/>} label="Nodo" help="Waypoint transitable del grafo." />
        <Tool tour="poi" active={tool === 'poi'} onClick={() => chooseTool('poi')} icon={<MapPin size={16}/>} label="Punto" help="Destino buscable como recepción o consultorio." />
        <Tool tour="edge" active={tool === 'edge'} onClick={() => chooseTool('edge')} icon={<GitBranch size={16}/>} label="Conexión" help="Une dos nodos transitables. Rumbo bloquea cruces de pared." />
        <Tool tour="connector" active={tool === 'connector'} onClick={() => chooseTool('connector')} icon={<ArrowUpDown size={16}/>} label="Entre pisos" help="Ascensor, escalera o rampa entre pisos." />
        <Tool tour="qr" active={tool === 'qr'} onClick={() => chooseTool('qr')} icon={<QrCode size={16}/>} label="QR" help="Fija una ubicación física a un nodo." />
      </div>
      <span className="tool-divider" />
      <div className="tool-group utility-group">
        <span className="tool-group-label">Utilidades</span>
        <Tool tour="measure" active={tool === 'measure'} onClick={() => chooseTool('measure')} icon={<Ruler size={16}/>} label="Medir" help="Solo inspecciona una distancia; no crea geometría." />
        <Tool tour="scale" active={tool === 'scale'} onClick={() => chooseTool('scale')} icon={<Scaling size={16}/>} label="Calibrar" help="Guarda la relación px/metro; no crea geometría." />
      </div>
      <span className="toolbar-grow" />
      <button className="tool-button auto-model-button" onClick={() => void runAutomaticModel()} disabled={autoGenerating} title="Propone una red editable usando contraste del plano y barreras existentes."><Sparkles size={16}/>{autoGenerating ? 'Analizando…' : 'Generar modelo'}</button>
      <button className="tool-button" onClick={undoWall} disabled={!model.walls.length && !draft} title="Cancela el punto activo o elimina la última pared (⌘/Ctrl+Z)."><Undo2 size={16}/> Deshacer pared</button>
    </div>

    <div className="model-layout">
      <section className="panel canvas-panel">
        <div className="canvas-stage"><div className="plan-frame">
          <img src={source} alt={floorplan.name} draggable={false} onLoad={(event) => setSize({ width: event.currentTarget.naturalWidth || 1000, height: event.currentTarget.naturalHeight || 700 })}/>
          <svg
            className={`model-overlay tool-${tool}`}
            viewBox={`0 0 ${size.width} ${size.height}`}
            preserveAspectRatio="none"
            onClick={clickCanvas}
            onPointerMove={pointerMove}
            onPointerUp={() => setDrag(null)}
            onPointerLeave={() => setDrag(null)}
          >
            {model.walls.map((wall) => <g key={wall.id} className={`wall-entity ${selection?.kind === 'wall' && selection.id === wall.id ? 'selected' : ''}`} onClick={(event) => { if (tool !== 'select') return; event.stopPropagation(); setSelection({ kind: 'wall', id: wall.id }) }}>
              <line className="wall-hitbox" x1={wall.start.x} y1={wall.start.y} x2={wall.end.x} y2={wall.end.y}/>
              <line className="wall-line" x1={wall.start.x} y1={wall.start.y} x2={wall.end.x} y2={wall.end.y}/>
            </g>)}
            {navigation.edges.map((edge) => { const a = nodes.get(edge.from_node_id); const b = nodes.get(edge.to_node_id); if (!a || !b) return null; const invalid = edgeIsInvalid(edge); return <g key={edge.id} className={`edge-entity ${invalid ? 'invalid' : ''} ${selection?.kind === 'edge' && selection.id === edge.id ? 'selected' : ''}`} onClick={(event) => { if (tool !== 'select') return; event.stopPropagation(); setSelection({ kind: 'edge', id: edge.id }) }}><line className="edge-hitbox" x1={a.position.x} y1={a.position.y} x2={b.position.x} y2={b.position.y}/><line className="edge-line" x1={a.position.x} y1={a.position.y} x2={b.position.x} y2={b.position.y}/></g> })}
            {model.nodes.map((node) => <g key={node.id} className={`map-node kind-${node.kind} ${edgeStart === node.id || connectorSource === node.id || qrNode === node.id || (selection?.kind === 'node' && selection.id === node.id) ? 'selected' : ''}`} transform={`translate(${node.position.x} ${node.position.y})`} onClick={(e) => clickNode(e, node)} onPointerDown={(e) => pointerDownNode(e, node)}><circle r="8"/><text x="11" y="4" className="map-label">{node.label}</text></g>)}
            {model.pois.map((poi) => <g key={poi.id} className={`poi-map-marker ${selection?.kind === 'poi' && selection.id === poi.id ? 'selected' : ''}`} transform={`translate(${poi.position.x} ${poi.position.y})`} onClick={(event) => { if (tool !== 'select') return; event.stopPropagation(); setSelection({ kind: 'poi', id: poi.id }) }} onPointerDown={(event) => { if (tool !== 'select') return; event.stopPropagation(); setSelection({ kind: 'poi', id: poi.id }); setDrag({ kind: 'poi', id: poi.id }) }}><circle r="9"/><text y="3">P</text><text className="map-label" x="12" y="4">{poi.name}</text></g>)}
            {positioning.qr_anchors.map((qr) => { const node = nodes.get(qr.node_id); return node ? <g key={qr.id} className="qr-map-marker" transform={`translate(${node.position.x - 16} ${node.position.y - 16})`}><rect x="-6" y="-6" width="12" height="12" rx="2"/><text y="3">Q</text></g> : null })}
            {selectedWall && tool === 'select' && <g className="wall-edit-handles"><circle cx={selectedWall.start.x} cy={selectedWall.start.y} r="7" onPointerDown={(event) => { event.stopPropagation(); setDrag({ kind: 'wall-start', id: selectedWall.id }) }}/><circle cx={selectedWall.end.x} cy={selectedWall.end.y} r="7" onPointerDown={(event) => { event.stopPropagation(); setDrag({ kind: 'wall-end', id: selectedWall.id }) }}/></g>}
            {draft && <circle className="guide-node" cx={draft.x} cy={draft.y} r="5"/>}
            {measure && <Guide points={measure} className="measure-line"/>}
            {scaleDraft && <Guide points={scaleDraft} className="calibration-line"/>}
          </svg>
          {measureText && <div className="floating-measure">{measureText}</div>}
        </div></div>
      </section>

      <aside className="panel inspector">
        <span className="panel-kicker">{selection ? 'Elemento seleccionado' : 'Herramienta'}</span>
        <h3>{selection ? selectionTitle(selection.kind) : title(tool)}</h3>
        {!selection && <p className="tool-explanation">{explain(tool)}</p>}
        {notice && <div className="inline-notice">{notice}</div>}

        {selectedNode && <div className="inspector-block emphasis"><label className="field"><span>Nombre</span><input value={selectedNode.label} onChange={(e) => updateNode({ label: e.target.value })}/></label><label className="field"><span>Tipo</span><select value={selectedNode.kind} onChange={(e) => updateNode({ kind: e.target.value as MapNode['kind'] })}><option value="waypoint">Waypoint</option><option value="decision">Decisión / giro</option><option value="entrance">Entrada</option></select></label><div className="selection-chip">Arrastra el nodo para recolocarlo.</div><button className="button full danger-button" onClick={() => removeNode(selectedNode.id)}><Trash2 size={14}/> Eliminar nodo</button></div>}
        {selectedWall && <div className="inspector-block emphasis"><div className="selection-chip">Arrastra cualquiera de los dos extremos para corregir la pared.</div><CoordinateFields wall={selectedWall} onChange={updateWall}/><button className="button full danger-button" onClick={() => removeWall(selectedWall.id)}><Trash2 size={14}/> Eliminar pared</button></div>}
        {selectedPoi && <div className="inspector-block emphasis"><label className="field"><span>Nombre</span><input value={selectedPoi.name} onChange={(e) => updatePoi({ name: e.target.value })}/></label><label className="field"><span>Categoría</span><input value={selectedPoi.category} onChange={(e) => updatePoi({ category: e.target.value })}/></label><label className="field"><span>Nodo asociado</span><select value={selectedPoi.node_id} onChange={(e) => updatePoi({ node_id: e.target.value })}>{model.nodes.map((node) => <option key={node.id} value={node.id}>{node.label}</option>)}</select></label><div className="selection-chip">También puedes arrastrar el punto en el plano.</div><button className="button full danger-button" onClick={() => removePoi(selectedPoi.id)}><Trash2 size={14}/> Eliminar punto</button></div>}
        {selectedEdge && <div className="inspector-block emphasis"><label className="field"><span>Tipo</span><select value={selectedEdge.kind} onChange={(e) => updateEdge({ kind: e.target.value as NavigationEdge['kind'] })}><option value="corridor">Pasadizo</option><option value="doorway">Puerta</option></select></label><label className="checkbox-field"><input type="checkbox" checked={selectedEdge.accessible} onChange={(e) => updateEdge({ accessible: e.target.checked })}/><span>Ruta accesible</span></label>{edgeIsInvalid(selectedEdge) && <div className="inline-notice danger-notice">Esta conexión atraviesa una pared y navegación la ignorará.</div>}<button className="button full danger-button" onClick={() => removeEdge(selectedEdge.id)}><Trash2 size={14}/> Eliminar conexión</button></div>}

        {!selection && tool === 'scale' && scaleDraft && <div className="inspector-block emphasis"><label className="field"><span>Distancia real (m)</span><input type="number" min="0.01" step="0.01" value={meters} onChange={(e) => setMeters(e.target.value)} autoFocus/></label><button className="button primary full" onClick={applyScale}><Check size={15}/> Calibrar</button></div>}
        {!selection && tool === 'poi' && poiDraft && <div className="inspector-block emphasis"><label className="field"><span>Nombre</span><input value={poiName} onChange={(e) => setPoiName(e.target.value)} placeholder="Consultorio 101"/></label><label className="field"><span>Categoría</span><input value={poiCategory} onChange={(e) => setPoiCategory(e.target.value)}/></label><div className="selection-chip">Nodo asociado: <strong>{nodes.get(poiDraft.nodeId)?.label}</strong></div><button className="button primary full" onClick={addPoi}>Crear punto</button></div>}
        {!selection && tool === 'connector' && connectorSource && <div className="inspector-block emphasis"><div className="selection-chip">Origen: <strong>{nodes.get(connectorSource)?.label}</strong></div><label className="field"><span>Tipo</span><select value={connectorKind} onChange={(e) => { const kind=e.target.value as ConnectorKind; setConnectorKind(kind); setConnectorLabel(kind==='elevator'?'Ascensor':kind==='stairs'?'Escalera':'Rampa') }}><option value="elevator">Ascensor</option><option value="stairs">Escalera</option><option value="ramp">Rampa</option></select></label><label className="field"><span>Etiqueta</span><input value={connectorLabel} onChange={(e) => setConnectorLabel(e.target.value)}/></label><label className="field"><span>Piso destino</span><select value={targetFloorId} onChange={(e) => setTargetFloorId(e.target.value)}><option value="">Seleccionar…</option>{siblingFloors.map((f) => <option key={f.id} value={f.id}>{f.floor_label}</option>)}</select></label><label className="field"><span>Nodo destino</span><select value={targetNodeId} onChange={(e) => setTargetNodeId(e.target.value)}><option value="">Seleccionar…</option>{targetNodes.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}</select></label><button className="button primary full" onClick={addConnector} disabled={!targetNodeId}>Vincular pisos</button></div>}
        {!selection && tool === 'qr' && qrNode && <div className="inspector-block emphasis"><div className="selection-chip">Nodo: <strong>{nodes.get(qrNode)?.label}</strong></div><label className="field"><span>Etiqueta</span><input value={qrLabel} onChange={(e) => setQrLabel(e.target.value)}/></label><label className="field"><span>Payload</span><input value={qrCode} onChange={(e) => setQrCode(e.target.value)}/></label><button className="button primary full" onClick={addQr}>Asociar QR</button></div>}

        {validationIssues.length > 0 && <div className="inspector-block validation-block"><span className="label">Validación de la propuesta</span><ul className="validation-list">{validationIssues.map((issue) => <li key={issue.code + issue.message} className={`validation-${issue.severity}`}>{issue.message}</li>)}</ul><button className="button ghost full" onClick={() => setValidationIssues([])}>Ocultar</button></div>}
        <div className="inspector-block"><span className="label">Escala activa</span><strong>{model.pixels_per_meter ? `${model.pixels_per_meter.toFixed(2)} px = 1 m` : 'No calibrada'}</strong><small>Medir es temporal. Calibrar sí guarda este factor, pero ninguno de los dos crea paredes, nodos o rutas.</small></div>
        <div className="mini-stats"><span><strong>{model.walls.length}</strong> paredes</span><span><strong>{model.nodes.length}</strong> nodos</span><span><strong>{model.pois.length}</strong> puntos</span><span><strong>{navigation.edges.length}</strong> conexiones</span></div>
      </aside>
    </div>
  </div>
}

function Tool({ active, onClick, icon, label, help, tour }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string; help: string; tour?: string }) {
  return <button type="button" className={`tool-button ${active ? 'active' : ''}`} onClick={onClick} title={help} data-tour={tour}>{icon}{label}</button>
}

function Guide({ points, className }: { points: [Point2D, Point2D]; className: string }) {
  const [a, b] = points
  return <g><line className={className} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/><circle className="guide-node" cx={a.x} cy={a.y} r="5"/><circle className="guide-node" cx={b.x} cy={b.y} r="5"/></g>
}

function CoordinateFields({ wall, onChange }: { wall: WallSegment; onChange: (patch: Partial<WallSegment>) => void }) {
  const number = (value: string, fallback: number) => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : fallback }
  return <div className="coordinate-grid">
    <label className="field"><span>Inicio X</span><input type="number" value={wall.start.x} onChange={(e) => onChange({ start: { ...wall.start, x: number(e.target.value, wall.start.x) } })}/></label>
    <label className="field"><span>Inicio Y</span><input type="number" value={wall.start.y} onChange={(e) => onChange({ start: { ...wall.start, y: number(e.target.value, wall.start.y) } })}/></label>
    <label className="field"><span>Fin X</span><input type="number" value={wall.end.x} onChange={(e) => onChange({ end: { ...wall.end, x: number(e.target.value, wall.end.x) } })}/></label>
    <label className="field"><span>Fin Y</span><input type="number" value={wall.end.y} onChange={(e) => onChange({ end: { ...wall.end, y: number(e.target.value, wall.end.y) } })}/></label>
  </div>
}

function selectionTitle(kind: NonNullable<Selection>['kind']) {
  return ({ node: 'Nodo', wall: 'Pared', poi: 'Punto de interés', edge: 'Conexión' })[kind]
}

function title(tool: Tool) {
  return ({ select:'Seleccionar y editar', wall:'Paredes', measure:'Medición', scale:'Calibración', node:'Nodos', poi:'Puntos de atención', edge:'Conexiones', connector:'Entre pisos', qr:'Puntos QR' })[tool]
}

function explain(tool: Tool) {
  return ({
    select:'Haz clic en una pared, nodo, punto o conexión. Puedes editarla desde este panel y arrastrar nodos, puntos y extremos de pared.',
    wall:'Una pared representa un límite físico. Al activar esta herramienta se resaltan todas las paredes. Esc cancela el punto activo y ⌘/Ctrl+Z deshace.',
    measure:'Utilidad temporal: marca dos puntos para comprobar una distancia. No modifica el modelo.',
    scale:'Utilidad de configuración: marca una distancia conocida y guarda la relación píxel/metro. No crea geometría.',
    node:'Los nodos son lugares transitables del grafo. Al activar esta herramienta se resaltan los nodos.',
    poi:'Los puntos (POI) son destinos buscables. Al activar esta herramienta se resaltan los puntos.',
    edge:'Una conexión indica que una persona puede desplazarse entre dos nodos. Rumbo impide crear una conexión que atraviese una pared modelada.',
    connector:'Une un nodo de este piso con otro piso mediante ascensor, escalera o rampa.',
    qr:'Asocia un QR físico a un nodo. Al escanearlo, la app conoce la posición inicial exacta.',
  })[tool]
}
