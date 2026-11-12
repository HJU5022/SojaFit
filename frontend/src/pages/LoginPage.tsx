import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { getDemoStatus, getGoogleStatus } from '../api/auth'
import type { DemoAccount } from '../api/auth'
import type { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthProvider'

function loginErrorMessage(error: unknown) {
  const api = error as Partial<ApiError> | null
  const messages: Record<string, string> = {
    UNAUTHORIZED: '로그인하지 못했습니다. 이메일과 비밀번호 또는 가입 방법을 확인해 주세요.',
    VALIDATION_ERROR: '이메일 형식과 비밀번호 입력을 확인해 주세요.',
    ORIGIN_MISMATCH: '로그인 요청을 허용할 수 없습니다. 공식 서비스 주소에서 다시 접속해 주세요.',
    FORBIDDEN: '로그인 요청을 허용할 수 없습니다. 공식 서비스 주소에서 다시 접속해 주세요.',
    RATE_LIMITED: '로그인 시도가 많습니다. 잠시 기다린 후 다시 시도해 주세요.',
    UNAVAILABLE: '로그인 서비스가 일시적으로 원활하지 않습니다. 잠시 후 다시 시도해 주세요.',
    UPSTREAM_ERROR: '로그인 서비스가 일시적으로 원활하지 않습니다. 잠시 후 다시 시도해 주세요.',
    INTERNAL_ERROR: '로그인 서비스가 일시적으로 원활하지 않습니다. 잠시 후 다시 시도해 주세요.',
    TIMEOUT: '로그인 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.',
    INVALID_RESPONSE: '로그인 서버 응답을 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    SESSION_CONFIRMATION_FAILED: '로그인 요청은 처리되었지만 로그인 상태를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  }
  const message = error instanceof TypeError ? '서비스에 연결하지 못했습니다. 네트워크 연결을 확인한 뒤 다시 시도해 주세요.'
    : messages[api?.code ?? ''] ?? '로그인 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'
  return api?.requestId ? `${message} (요청 ID: ${api.requestId})` : message
}

export default function LoginPage() {
  const auth = useAuth()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [agreed, setAgreed] = useState(false)
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
  const failure = error || auth.error
  const credentialsFailed = (failure as Partial<ApiError> | null)?.code === 'UNAUTHORIZED'
  return <div className="public-site login-page">
    <header className="public-header"><Link className="public-brand" to="/"><img className="brand-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT" width="174" height="48" /></Link><Link className="public-secondary" to="/">서비스 소개</Link></header>
    <div className="public-auth-grid">
    <aside className="public-auth-story"><h2>회로를 이해하고,<br />근거로 검토하세요.</h2><p>교체할 부품과 사용 조건을 확인하고, 대체 후보의 판정 근거를 함께 살펴보세요.</p><img className="public-auth-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT 브랜드 로고" width="920" height="256" /><p className="public-auth-caption">회로 맥락 / 후보 비교 / 문서 근거</p></aside>
    <section className="public-auth-form"><div className="public-auth-content">
    <h1>SojaFit에 로그인</h1><p>내 회로 프로젝트와 분석을 시작하세요.</p>
    {auth.accountDeleted && <p className="login-deletion-notice" role="status">계정 삭제가 완료되었습니다. 탈퇴한 계정으로는 로그인할 수 없습니다. 다시 이용하려면 Google로 새로 가입해 주세요.</p>}
    {import.meta.env.DEV && demo && <div role="group" aria-label="데모 로그인"><p>데모 모드: 비밀번호 없이 로컬 데모 전용 계정으로 들어갑니다(평가 계정 아님). A · B는 서로 다른 사용자입니다.</p>
      <button type="button" disabled={busy} onClick={() => void enterDemo('a')}>데모 사용자 A로 들어가기</button>{' '}
      <button type="button" disabled={busy} onClick={() => void enterDemo('b')}>데모 사용자 B로 들어가기</button></div>}
    {google && <><form aria-label="Google 로그인" method="get" action="/api/auth/google/start" onSubmit={event => { if (!agreed) event.preventDefault() }}>
      <label className="consent"><input type="checkbox" checked={agreed} onChange={event => setAgreed(event.target.checked)} /><span><Link to="/privacy">개인정보처리방침</Link>을 확인했고 개인정보 수집 · 이용에 동의합니다.</span></label>
      <input type="hidden" name="consent" value="1" disabled={!agreed} />
      <button className="public-google" type="submit" disabled={busy || !agreed}>Google 로그인</button>
    </form><div className="public-auth-separator">또는</div></>}
    <form onSubmit={(event) => void submit(event)}>
      <label htmlFor="email">이메일</label>
      <input id="email" type="email" autoComplete="username" required maxLength={100} value={email} onChange={(event) => setEmail(event.target.value)} />
      <label htmlFor="password">비밀번호</label>
      <input id="password" type="password" autoComplete="current-password" required maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} />
      <button disabled={busy} type="submit">{busy ? '로그인 확인 중…' : '로그인'}</button>
    </form>
    {failure ? <div className="login-error" role="alert"><p>{loginErrorMessage(failure)}</p>
      {credentialsFailed && <ul><li>탈퇴했거나 아직 가입하지 않았다면 회원가입이 필요합니다.</li>{google && <li>Google로 가입했다면 Google 로그인을 이용하세요.</li>}<li>반복해서 실패했다면 잠시 멈추고 15분 뒤 다시 시도해 주세요.</li></ul>}
    </div> : params.get('google') === 'consent' ? <p role="alert">개인정보 수집 · 이용에 동의해야 Google로 가입할 수 있습니다.</p> : params.get('google') === 'error' && <div className="login-error" role="alert"><p>Google 로그인을 확인할 수 없습니다. 다시 시도해 주세요.</p><p>계정 선택이나 동의를 취소했다면 Google 로그인을 다시 시작하세요. 오류가 계속되면 잠시 후 다시 시도해 주세요.</p></div>}
    {import.meta.env.DEV && <p className="public-auth-note">처음 이용하시나요? <Link to="/signup">회원가입</Link></p>}
    {!google && <p className="public-legal"><Link to="/privacy">개인정보처리방침</Link></p>}
    {googleUnavailable && <p className="panel-note">Google 로그인 연결 상태를 확인하지 못했습니다. 잠시 후 다시 시도하거나 이메일 로그인을 이용하세요.</p>}
    </div></section></div>
  </div>
}
