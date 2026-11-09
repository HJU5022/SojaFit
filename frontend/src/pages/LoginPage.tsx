import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { getDemoStatus, getGoogleStatus } from '../api/auth'
import type { DemoAccount } from '../api/auth'
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
  const [demo, setDemo] = useState(false)
  useEffect(() => {
    let current = true
    getGoogleStatus().then(({ enabled }) => { if (current) setGoogle(enabled) }).catch(() => {})
    // 데모 모드가 아니면 404라 버튼을 숨긴 그대로 둔다
    getDemoStatus().then(({ enabled }) => { if (current) setDemo(enabled) }).catch(() => {})
    return () => { current = false }
  }, [])
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError(null)
    try { await auth.login(email, password) } catch (error) { setError(error) }
    finally { setPassword(''); setBusy(false) }
  }
  async function enterDemo(account: DemoAccount) {
    if (busy) return
    setBusy(true); setError(null)
    try { await auth.demoLogin(account) } catch (error) { setError(error) }
    finally { setBusy(false) }
  }
  if (auth.loading) return <p role="status">로그인 상태 확인 중입니다.</p>
  if (auth.user) return <Navigate to="/app" replace />
  return <section className="panel login-panel">
    <h1>로그인</h1><p>회로 검토를 시작하는 곳입니다.</p>
    {demo && <div role="group" aria-label="데모 로그인"><p>데모 모드: 비밀번호 없이 로컬 데모 전용 계정으로 들어갑니다(평가 계정 아님). A · B는 서로 다른 사용자입니다.</p>
      <button type="button" disabled={busy} onClick={() => void enterDemo('a')}>데모 사용자 A로 들어가기</button>{' '}
      <button type="button" disabled={busy} onClick={() => void enterDemo('b')}>데모 사용자 B로 들어가기</button></div>}
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
