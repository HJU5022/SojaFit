import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import * as auth from '../api/auth'
import type { ApiError } from '../api/client'

type Auth = {
  user: auth.User | null; loading: boolean; error: unknown
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  deleteAccount: () => Promise<void>
}
const AuthContext = createContext<Auth | null>(null)
const DUMMY_USER: auth.User = { user_id: 0, role: 'user' }

export function dummyAuthEnabled(env: { DEV: boolean; MODE?: string; VITE_DUMMY_AUTH?: string }) {
  return env.DEV && (env.MODE === 'dummy' || env.VITE_DUMMY_AUTH === '1')
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const dummy = dummyAuthEnabled(import.meta.env)
  const client = useQueryClient()
  const [user, setUser] = useState<auth.User | null>(dummy ? DUMMY_USER : null)
  const [loading, setLoading] = useState(!dummy)
  const [error, setError] = useState<unknown>(null)
  // [왜] 공용 PC에서 다음 사람이 앞 사람의 회로 · 대화 · 설정을 보지 않게, 로그인 상태를 잃으면(로그아웃 · 탈퇴 · 세션 만료)
  // 화면 메모리(React Query 캐시)와 탭 저장소를 비운다. 주소의 projectId · targetRef는 보호 화면이 /login으로 바꿔(replace) 지운다
  function endSession() {
    client.clear()
    try { sessionStorage.clear() } catch { /* 저장소를 막은 브라우저: 지울 것도 없다 */ }
    setUser(null)
    setError(null)
  }
  useEffect(() => {
    if (dummy) return
    let current = true
    const controller = new AbortController()
    const expire = () => { client.clear(); try { sessionStorage.clear() } catch { /* 위와 같음 */ } setUser(null) }
    window.addEventListener('sojafit:session-expired', expire)
    auth.getMe(controller.signal).then((user) => { if (current) setUser(user) }).catch((error: ApiError) => {
      if (current && error.code !== 'UNAUTHORIZED') setError(error)
    }).finally(() => { if (current) setLoading(false) })
    return () => { current = false; controller.abort(); window.removeEventListener('sojafit:session-expired', expire) }
  }, [dummy, client])
  async function login(email: string, password: string) {
    if (dummy) { setUser(DUMMY_USER); setError(null); return }
    await auth.login(email, password)
    setUser(await auth.getMe())
    setError(null)
  }
  async function signup(email: string, password: string) {
    if (dummy) { setUser(DUMMY_USER); setError(null); return }
    await auth.signup(email, password)
    setUser(await auth.getMe())
    setError(null)
  }
  async function logout() {
    if (dummy) { endSession(); return }
    await auth.logout()
    endSession()
  }
  async function deleteAccount() {
    if (dummy) { endSession(); return }
    await auth.deleteAccount()
    endSession()
  }
  return <AuthContext.Provider value={{ user, loading, error, login, signup, logout, deleteAccount }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('AuthProvider is required')
  return auth
}
