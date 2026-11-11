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
  const [googleUnavailable, setGoogleUnavailable] = useState(false)
  useEffect(() => {
    let current = true
    getGoogleStatus().then(({ enabled }) => { if (current) setGoogle(enabled) }).catch(() => { if (current) setGoogleUnavailable(true) })
    if (import.meta.env.DEV) getDemoStatus().then(({ enabled }) => { if (current) setDemo(enabled) }).catch(() => {})
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
  return <div className="public-site login-page">
    <header className="public-header"><Link className="public-brand" to="/"><img className="brand-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT" width="174" height="48" /></Link><Link className="public-secondary" to="/">서비스 소개</Link></header>
    <div className="public-auth-grid">
    <aside className="public-auth-story"><h2>회로를 이해하고,<br />근거로 검토하세요.</h2><p>교체할 부품과 사용 조건을 확인하고, 대체 후보의 판정 근거를 함께 살펴보세요.</p><img className="public-auth-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT 브랜드 로고" width="920" height="256" /><p className="public-auth-caption">회로 맥락 / 후보 비교 / 문서 근거 / 사람 승인</p></aside>
    <section className="public-auth-form"><div className="public-auth-content">
    <h1>SojaFit에 로그인</h1><p>내 회로 프로젝트와 분석을 시작하세요.</p>
    {import.meta.env.DEV && demo && <div role="group" aria-label="데모 로그인"><p>데모 모드: 비밀번호 없이 로컬 데모 전용 계정으로 들어갑니다(평가 계정 아님). A · B는 서로 다른 사용자입니다.</p>
      <button type="button" disabled={busy} onClick={() => void enterDemo('a')}>데모 사용자 A로 들어가기</button>{' '}
      <button type="button" disabled={busy} onClick={() => void enterDemo('b')}>데모 사용자 B로 들어가기</button></div>}
    {google && <><a className="public-secondary public-google" href="/api/auth/google/start">Google로 계속하기</a><div className="public-auth-separator">또는</div></>}
    <form onSubmit={(event) => void submit(event)}>
      <label htmlFor="email">이메일</label>
      <input id="email" type="email" autoComplete="username" required maxLength={100} value={email} onChange={(event) => setEmail(event.target.value)} />
      <label htmlFor="password">비밀번호</label>
      <input id="password" type="password" autoComplete="current-password" required maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} />
      <button disabled={busy} type="submit">{busy ? '로그인 확인 중…' : '로그인'}</button>
    </form>
    {(error || auth.error) ? <p role="alert">{errorMessage(error || auth.error)}</p>
      : params.get('google') === 'error' && <p role="alert">Google 로그인을 확인할 수 없습니다. 다시 시도해 주세요.</p>}
    <p className="public-auth-note">처음 이용하시나요? <Link to="/signup">회원가입</Link></p>
    {googleUnavailable && <p className="panel-note">Google 로그인을 사용할 수 없습니다. 이메일 로그인으로 진행해 주세요.</p>}
    </div></section></div>
  </div>
}
