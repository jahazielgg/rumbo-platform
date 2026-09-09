import { UserRound } from 'lucide-react'
import { PageHeader } from '../../../shared/components/PageHeader'

export function ProfilePage() {
  return <div className="page"><PageHeader eyebrow="Sistema" title="Perfil" description="La autenticación real queda fuera del primer corte del MVP." />
    <div className="panel profile-card"><div className="profile-avatar"><UserRound size={28}/></div><div><span className="panel-kicker">Administrador</span><h2>Rumbo Pilot</h2><p>Perfil local de demostración.</p></div></div>
  </div>
}
