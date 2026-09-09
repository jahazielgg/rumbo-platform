import type { ReactNode } from 'react'
import { Compass, DraftingCompass, FileStack, Navigation2, Settings, UserRound } from 'lucide-react'
import { NavLink } from 'react-router-dom'

function NavItem({ to, icon, label, tourId }: { to: string; icon: ReactNode; label: string; tourId?: string }) {
  return <NavLink to={to} data-tour={tourId} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}><span className="nav-icon">{icon}</span><span>{label}</span></NavLink>
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Compass size={19} strokeWidth={2.4} /></div><div><strong>Rumbo</strong><span>Indoor mapping</span></div></div>
        <div className="workspace-card"><div className="workspace-avatar">RP</div><div><span className="eyebrow">Workspace</span><strong>Rumbo Pilot</strong></div></div>
        <nav>
          <div className="nav-section"><NavItem to="/modelado" icon={<DraftingCompass size={18} />} label="Modelado" /><NavItem to="/navegacion" tourId="navigation" icon={<Navigation2 size={18} />} label="Navegación" /></div>
          <div className="nav-divider" />
          <div className="nav-section"><NavItem to="/planos" icon={<FileStack size={18} />} label="Planos" /></div>
          <div className="nav-section nav-bottom"><NavItem to="/configuracion" icon={<Settings size={18} />} label="Configuración" /><NavItem to="/perfil" icon={<UserRound size={18} />} label="Perfil" /></div>
        </nav>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  )
}
