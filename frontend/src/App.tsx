import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { AuthProvider, useAuth } from './auth/AuthProvider'
import RequireAuth from './auth/RequireAuth'
import { dummyFlowEnabled, errorMessage } from './api/client'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import EmailActionPage from './pages/EmailActionPage'
import AdminUsersPage from './pages/AdminUsersPage'
import WorkbenchPage from './pages/WorkbenchPage'
import LandingPage from './pages/LandingPage'
import PrivacyPage from './pages/PrivacyPage'
import SettingsPage from './pages/SettingsPage'
import AccountMenu from './components/AccountMenu'
import useOverlayScrollbar from './hooks/useOverlayScrollbar'

export default function App() {
  return <AuthProvider><Shell /></AuthProvider>
}

export function DummyModeNotice({ enabled }: { enabled: boolean }) {
  return enabled ? <p className="dummy-mode-notice" role="status">더미 실행 모드 · 저장되지 않음</p> : null
}

function Shell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const workbench = location.pathname === '/app'
  const settings = location.pathname === '/settings'
  const publicPage = ['/', '/login', '/signup', '/privacy', '/verify-email', '/reset-password'].includes(location.pathname)
  const ContentRoot = workbench ? 'div' : 'main'
  useOverlayScrollbar()
  async function signOut() {
    if (busy) return
    setBusy(true); setError(null)
    try { await logout() } catch (error) { setError(error) }
    finally { setBusy(false) }
  }
  return (
    <div className={`shell${publicPage ? ' public-shell' : ''}${workbench ? ' workbench-host' : ''}${settings ? ' settings-host' : ''}`}>
      {settings ? <header className="app-topbar settings-topbar">
        <a className="brand workbench-brand" href="/app"><img className="brand-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT" width="142" height="40" /></a>
        <nav className="settings-header-context" aria-label="현재 위치"><NavLink to="/app">작업대</NavLink><svg aria-hidden="true" viewBox="0 0 20 20"><path d="m8 5 5 5-5 5" /></svg><span aria-current="page">내 설정</span></nav>
        <AccountMenu user={user ?? undefined} onLogout={signOut} logoutBusy={busy} />
      </header> : !workbench && !publicPage && <header className="topbar">
        <a className="brand" href="/">
          <img className="brand-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT" width="142" height="40" />
        </a>
        <nav aria-label="주요 화면">
          <NavLink to="/app">작업대</NavLink>
          {!user && <NavLink to="/login">로그인</NavLink>}
          {user && <NavLink to="/settings">내 설정</NavLink>}
          {user?.role === 'admin' && <NavLink to="/admin/users">사용자 관리</NavLink>}
          {user && <button disabled={busy} onClick={() => void signOut()}>{busy ? '로그아웃 중…' : '로그아웃'}</button>}
        </nav>
      </header>}
      <DummyModeNotice enabled={dummyFlowEnabled(import.meta.env)} />
      <ContentRoot id="main" className={workbench ? 'workbench-page' : settings ? 'settings-main' : ''}>
        {error ? <p role="alert">{errorMessage(error)}</p> : null}
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/verify-email" element={<EmailActionPage key="verify" purpose="signup" />} />
          <Route path="/reset-password" element={<EmailActionPage key="reset" purpose="reset" />} />
          <Route path="/app" element={<RequireAuth><WorkbenchPage user={user ?? undefined} onLogout={signOut} logoutBusy={busy} /></RequireAuth>} />
          <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
          <Route path="/admin/users" element={<AdminUsersPage />} />
        </Routes>
      </ContentRoot>
    </div>
  )
}
