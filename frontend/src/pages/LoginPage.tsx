import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { getDemoStatus, getGoogleStatus } from '../api/auth'
import type { DemoAccount } from '../api/auth'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { PrivacyNotice } from './SignupPage'

export default function LoginPage() {
  const auth = useAuth()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [google, setGoogle] = useState(false)
  const [demo, setDemo] = useState(false)
  const [agreed, setAgreed] = useState(false)
  const [googleUnavailable, setGoogleUnavailable] = useState(false)
  useEffect(() => {
    let current = true
    getGoogleStatus().then(({ enabled }) => { if (current) setGoogle(enabled) }).catch(() => { if (current) setGoogleUnavailable(true) })
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
    {google && <section className="google-start" aria-label="Google로 시작하기">
      <h2>Google로 시작하기</h2>
      <p>Google 계정으로 가입하고 로그인합니다. Google이 확인한 이메일만 받습니다.</p>
      <PrivacyNotice />
      <label className="consent"><input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} />
        위 안내를 읽었고 개인정보 수집 · 이용에 동의합니다(필수)</label>
      {/* [왜] 동의했다는 표시(consent=1)를 서버가 받아야 처음 오는 계정을 만든다. 체크 전에는 버튼이 꺼져 있다 */}
      <form method="get" action="/api/auth/google/start">
        <input type="hidden" name="consent" value="1" />
        <button type="submit" disabled={!agreed}>Google로 시작하기</button>
      </form>
    </section>}
    <p>{google ? '평가용 · 관리자 계정은 이메일과 비밀번호로 로그인합니다.' : '이메일과 비밀번호로 로그인합니다.'}</p>
    <form onSubmit={(event) => void submit(event)}>
      <label htmlFor="email">이메일</label>
      <input id="email" type="email" autoComplete="username" required maxLength={100} value={email} onChange={(event) => setEmail(event.target.value)} />
      <label htmlFor="password">비밀번호</label>
      <input id="password" type="password" autoComplete="current-password" required maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} />
      <button disabled={busy} type="submit">{busy ? '로그인 확인 중…' : '로그인'}</button>
    </form>
    {(error || auth.error) ? <p role="alert">{errorMessage(error || auth.error)}</p>
      : params.get('google') === 'consent' ? <p role="alert">개인정보 수집 · 이용에 동의해야 Google로 가입할 수 있습니다.</p>
      : params.get('google') === 'error' && <p role="alert">Google 로그인을 확인할 수 없습니다. 다시 시도해 주세요.</p>}
    {demo && <p>처음이면 <Link to="/signup">가입</Link>(로컬 데모 전용)</p>}
    {google && <p><a href="/api/auth/google/start">Google 관리자 로그인</a></p>}
    {googleUnavailable && <p className="panel-note">Google 로그인을 사용할 수 없습니다. 이메일 로그인으로 진행해 주세요.</p>}
  </section>
}
