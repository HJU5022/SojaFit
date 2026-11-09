import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import * as auth from '../api/auth'
import type { ApiError } from '../api/client'

type Auth = {
  user: auth.User | null; loading: boolean; error: unknown
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}
const AuthContext = createContext<Auth | null>(null)
const DUMMY_USER: auth.User = { user_id: 0, role: 'user' }

export function dummyAuthEnabled(env: { DEV: boolean; MODE?: string; VITE_DUMMY_AUTH?: string }) {
  return env.DEV && (env.MODE === 'dummy' || env.VITE_DUMMY_AUTH === '1')
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const dummy = dummyAuthEnabled(import.meta.env)
  const [user, setUser] = useState<auth.User | null>(dummy ? DUMMY_USER : null)
  const [loading, setLoading] = useState(!dummy)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    if (dummy) return
    let current = true
    const controller = new AbortController()
    const expire = () => setUser(null)
    window.addEventListener('sojafit:session-expired', expire)
    auth.getMe(controller.signal).then((user) => { if (current) setUser(user) }).catch((error: ApiError) => {
      if (current && error.code !== 'UNAUTHORIZED') setError(error)
    }).finally(() => { if (current) setLoading(false) })
    return () => { current = false; controller.abort(); window.removeEventListener('sojafit:session-expired', expire) }
  }, [dummy])
  async function login(email: string, password: string) {
    if (dummy) { setUser(DUMMY_USER); setError(null); return }
    await auth.login(email, password)
    setUser(await auth.getMe())
    setError(null)
  }
  async function logout() {
    if (dummy) { setUser(null); setError(null); return }
    await auth.logout()
    setUser(null)
    setError(null)
  }
  return <AuthContext.Provider value={{ user, loading, error, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('AuthProvider is required')
  return auth
}
