import { api } from '../../../shared/api/http'
import type { NavigationConfig } from '../../navigation/domain/navigation'
import type { SpatialModel } from '../domain/model'

export interface StructuralPolygon { outer: Array<{ x: number; y: number }>; holes: Array<Array<{ x: number; y: number }>> }

export interface ValidationIssue { code: string; severity: 'error' | 'warning' | 'info'; message: string; subjects: string[] }

export interface ValidationReport { status: 'ok' | 'warnings' | 'errors'; issues: ValidationIssue[]; metrics: Record<string, number> }

export interface AutomaticModelResult {
  model: SpatialModel
  navigation: NavigationConfig
  structural: {
    parser: string
    parser_version: string
    image_width: number
    image_height: number
    wall_polygons: number
    obstacles: StructuralPolygon[]
    doors: Array<{ id: string; kind: 'door' | 'entrance' | 'passage'; confidence: number; width_px: number; polygon: StructuralPolygon; spaces: Array<string | null> }>
    windows: number
    spaces: Array<{ id: string; kind: string; label: string | null; connector_kind: string | null; confidence: number; polygon: StructuralPolygon }>
    walkable_areas: number
    validation: ValidationReport
    estimated_pixels_per_meter: number | null
    scale_source: string | null
  }
  diagnostics: {
    wallsDetected: number
    obstacles: number
    doors: number
    entrances: number
    windows: number
    spaces: number
    nodes: number
    edges: number
    rejectedByWalls: number
    backend: string
  }
}

interface AutoModelApiResponse {
  model: SpatialModel
  navigation: NavigationConfig
  structural: AutomaticModelResult['structural']
  diagnostics: Record<string, number | string>
}

const asNumber = (value: number | string | undefined, fallback = 0) => (typeof value === 'number' ? value : fallback)

/**
 * Structural Mapping v3 runs entirely on the server. The mapper reads vector geometry
 * when the plan is a PDF/SVG, runs multi-scale ML + classical perception on rasters,
 * infers walls / openings / spaces, and derives a sparse semantic navigation graph
 * that is validated against the walls before it is proposed to the editor.
 */
export async function generateAutomaticModel(
  _source: string,
  current: SpatialModel,
  _navigation: NavigationConfig,
  _naturalSize: { width: number; height: number },
): Promise<AutomaticModelResult> {
  const result = await api<AutoModelApiResponse>(`/api/v1/modeling/${current.floorplan_id}/auto-model`, {
    method: 'POST',
  })
  const d = result.diagnostics
  return {
    model: result.model,
    navigation: result.navigation,
    structural: result.structural,
    diagnostics: {
      wallsDetected: asNumber(d.wall_polygons, result.structural.wall_polygons),
      obstacles: asNumber(d.obstacles, result.structural.obstacles?.length ?? 0),
      doors: asNumber(d.doors, result.structural.doors.length),
      entrances: asNumber(d.entrances, result.structural.doors.filter((item) => item.kind === 'entrance').length),
      windows: asNumber(d.windows, result.structural.windows),
      spaces: asNumber(d.spaces, result.structural.spaces.length),
      nodes: asNumber(d.nodes, result.model.nodes.length),
      edges: asNumber(d.edges, result.navigation.edges.length),
      rejectedByWalls: asNumber(d.edges_rejected_by_walls, 0),
      backend: typeof d.backend === 'string' ? d.backend : 'unknown',
    },
  }
}

export function summarizeProposal(result: AutomaticModelResult): string {
  const { diagnostics, structural } = result
  const parts = [
    `${diagnostics.nodes} nodos y ${diagnostics.edges} conexiones`,
    `${diagnostics.spaces} espacios`,
    `${diagnostics.doors} puertas`,
    `${diagnostics.entrances} entradas`,
  ]
  const validation = structural.validation
  const errors = validation.issues.filter((issue) => issue.severity === 'error').length
  const warnings = validation.issues.filter((issue) => issue.severity === 'warning').length
  let status = 'Validación correcta.'
  if (errors) status = `${errors} errores de validación: corrígelos antes de guardar.`
  else if (warnings) status = `${warnings} avisos de validación para revisar.`
  const scale = !result.model.pixels_per_meter && structural.estimated_pixels_per_meter
    ? ` Escala estimada: ${structural.estimated_pixels_per_meter.toFixed(1)} px/m (calibra para confirmarla).`
    : ''
  return `Propuesta creada: ${parts.join(', ')}. ${status}${scale} Revisa y edita antes de guardar.`
}
