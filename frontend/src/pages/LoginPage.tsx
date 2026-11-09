import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { getGoogleStatus } from '../api/auth'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthProvider'

export default function LoginPage() {
  const auth = useAuth()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [google, setGoogle] = useState(false)
  useEffect(() => {
    let current = true
    getGoogleStatus().then(({ enabled }) => { if (current) setGoogle(enabled) }).catch(() => {})
    return () => { current = false }
  }, [])
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError(null)
    try { await auth.login(email, password) } catch (error) { setError(error) }
    finally { setPassword(''); setBusy(false) }
  }
  if (auth.loading) return <p role="status">로그인 상태 확인 중입니다.</p>
  if (auth.user) return <Navigate to="/app" replace />
  return <section className="panel login-panel">
    <h1>로그인</h1><p>회로 검토를 시작하는 곳입니다.</p>
    <form onSubmit={(event) => void submit(event)}>
      <label htmlFor="email">이메일</label>
      <input id="email" type="email" autoComplete="username" required maxLength={100} value={email} onChange={(event) => setEmail(event.target.value)} />
      <label htmlFor="password">비밀번호</label>
      <input id="password" type="password" autoComplete="current-password" required maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} />
      <button disabled={busy} type="submit">{busy ? '로그인 확인 중…' : '로그인'}</button>
    </form>
    {(error || auth.error) ? <p role="alert">{errorMessage(error || auth.error)}</p>
      : params.get('google') === 'error' && <p role="alert">Google 로그인을 확인할 수 없습니다. 다시 시도해 주세요.</p>}
    <p>처음이면 <Link to="/signup">가입</Link></p>
    {google && <p><a href="/api/auth/google/start">Google 관리자 로그인</a></p>}
  </section>
}
