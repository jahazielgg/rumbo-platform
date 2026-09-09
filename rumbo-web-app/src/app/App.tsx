import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '../shared/components/AppShell'
import { ModelingPage } from '../modules/modeling/presentation/ModelingPage'
import { FloorplansPage } from '../modules/floorplans/presentation/FloorplansPage'
import { NavigationPage } from '../modules/navigation/presentation/NavigationPage'
import { SettingsPage } from '../modules/settings/presentation/SettingsPage'
import { ProfilePage } from '../modules/profile/presentation/ProfilePage'

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/modelado" replace />} />
        <Route path="/modelado" element={<ModelingPage />} />
        <Route path="/navegacion" element={<NavigationPage />} />
        <Route path="/planos" element={<FloorplansPage />} />
        <Route path="/configuracion" element={<SettingsPage />} />
        <Route path="/perfil" element={<ProfilePage />} />
      </Routes>
    </AppShell>
  )
}
