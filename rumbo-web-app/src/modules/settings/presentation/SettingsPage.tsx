import { Database, Server, SlidersHorizontal } from 'lucide-react'
import { PageHeader } from '../../../shared/components/PageHeader'

export function SettingsPage() {
  return <div className="page"><PageHeader eyebrow="Sistema" title="Configuración" description="Parámetros técnicos del workspace." />
    <div className="cards-grid">
      <div className="panel info-card"><Server/><span>API</span><strong>FastAPI modular monolith</strong><small>REST · /api/v1</small></div>
      <div className="panel info-card"><Database/><span>Persistencia</span><strong>PostgreSQL + PostGIS</strong><small>Alembic migrations</small></div>
      <div className="panel info-card"><SlidersHorizontal/><span>Editor</span><strong>SVG overlay</strong><small>2D first · 3D projection next</small></div>
    </div>
  </div>
}
