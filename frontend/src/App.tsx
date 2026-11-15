import { MotionConfig } from 'motion/react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import RequireAuth from './auth/RequireAuth'
import DeploymentUpdate from './components/DeploymentUpdate'
import AdminUsersPage from './pages/AdminUsersPage'
import EmailActionPage from './pages/EmailActionPage'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import PrivacyPage from './pages/PrivacyPage'
import SettingsPage from './pages/SettingsPage'
import SignupPage from './pages/SignupPage'
import WorkbenchPage from './pages/WorkbenchPage'

export default function App() {
  return <MotionConfig reducedMotion="user"><AuthProvider>
    <DeploymentUpdate />
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/verify-email" element={<EmailActionPage key="verify" purpose="signup" />} />
      <Route path="/reset-password" element={<EmailActionPage key="reset" purpose="reset" />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
      <Route path="/admin/users" element={<RequireAuth admin><AdminUsersPage /></RequireAuth>} />
      <Route path="/app" element={<RequireAuth><WorkbenchPage /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </AuthProvider></MotionConfig>
}
