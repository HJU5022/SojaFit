import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { useState } from 'react'
import { AuthProvider, useAuth } from './auth/AuthProvider'
import RequireAuth from './auth/RequireAuth'
import { errorMessage } from './api/client'
import LoginPage from './pages/LoginPage'
import AdminUsersPage from './pages/AdminUsersPage'
import WorkbenchPage from './pages/WorkbenchPage'

export default function App() {
  return <AuthProvider><Shell /></AuthProvider>
}

function Shell() {
  const { user, logout } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  async function signOut() {
    if (busy) return
    setBusy(true); setError(null)
    try { await logout() } catch (error) { setError(error) }
    finally { setBusy(false) }
  }
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/app">
          <svg aria-hidden="true" viewBox="0 0 48 20"><path d="M5 10h15l8-6v12l-8-6h23" /><circle cx="5" cy="10" r="3" /><circle cx="43" cy="10" r="3" /></svg>
          SojaFit
        </a>
        <nav aria-label="주요 화면">
          <NavLink to="/app">작업대</NavLink>
          {!user && <NavLink to="/login">로그인</NavLink>}
          {user?.role === 'admin' && <NavLink to="/admin/users">사용자 관리</NavLink>}
          {user && <button disabled={busy} onClick={() => void signOut()}>{busy ? '로그아웃 중…' : '로그아웃'}</button>}
        </nav>
      </header>
      <main id="main">
        {error ? <p role="alert">{errorMessage(error)}</p> : null}
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/app" element={<RequireAuth><WorkbenchPage /></RequireAuth>} />
          <Route path="/admin/users" element={<AdminUsersPage />} />
        </Routes>
      </main>
    </div>
  )
}
