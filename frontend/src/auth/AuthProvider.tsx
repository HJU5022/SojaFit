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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<auth.User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    let current = true
    const expire = () => setUser(null)
    window.addEventListener('sojafit:session-expired', expire)
    auth.getMe().then((user) => { if (current) setUser(user) }).catch((error: ApiError) => {
      if (current && error.code !== 'UNAUTHORIZED') setError(error)
    }).finally(() => { if (current) setLoading(false) })
    return () => { current = false; window.removeEventListener('sojafit:session-expired', expire) }
  }, [])
  async function login(email: string, password: string) {
    await auth.login(email, password)
    setUser(await auth.getMe())
    setError(null)
  }
  async function logout() {
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
