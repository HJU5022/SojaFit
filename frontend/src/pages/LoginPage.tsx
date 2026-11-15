import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useSearchParams } from 'react-router-dom'
import { getDemoStatus, getGoogleOnboarding, getGoogleStatus } from '../api/auth'
import type { DemoAccount } from '../api/auth'
import { errorMessage, requestIdProps } from '../api/client'
import type { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import AuthCard from '../components/AuthCard'

const SERVICE_DOWN = '로그인 서비스가 일시적으로 원활하지 않습니다. 잠시 후 다시 시도해 주세요.'
const RETURN_KEY = 'sojafit:login-return'
const NOT_ALLOWED = '로그인 요청을 허용할 수 없습니다. 공식 서비스 주소에서 다시 접속해 주세요.'
const MESSAGES: Record<string, string> = {
  UNAUTHORIZED: '로그인하지 못했습니다. 이메일과 비밀번호 또는 가입 방법을 확인해 주세요.',
  VALIDATION_ERROR: '이메일 형식과 비밀번호 입력을 확인해 주세요.',
  ORIGIN_MISMATCH: NOT_ALLOWED, FORBIDDEN: NOT_ALLOWED,
  RATE_LIMITED: '로그인 시도가 많습니다. 잠시 기다린 후 다시 시도해 주세요.',
  UNAVAILABLE: SERVICE_DOWN, UPSTREAM_ERROR: SERVICE_DOWN, INTERNAL_ERROR: SERVICE_DOWN,
  TIMEOUT: '로그인 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.',
  INVALID_RESPONSE: '로그인 서버 응답을 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  SESSION_CONFIRMATION_FAILED: '로그인 요청은 처리되었지만 로그인 상태를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
}
function loginErrorMessage(error: unknown) {
  const api = error as Partial<ApiError> | null
  const message = error instanceof TypeError ? '서비스에 연결하지 못했습니다. 네트워크 연결을 확인한 뒤 다시 시도해 주세요.'
    : MESSAGES[api?.code ?? ''] ?? '로그인 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'
  return message
}

// 폼 제출이라 Enter로 로그인된다.
export default function LoginPage() {
  const auth = useAuth()
  const location = useLocation()
  const [params] = useSearchParams()
  const [returnTo] = useState(() => {
    let stored: string | null = null
    try { stored = sessionStorage.getItem(RETURN_KEY) } catch { /* 저장소 없이 경로 상태만 사용한다. */ }
    const value: unknown = location.state?.returnTo ?? stored
    return typeof value === 'string' && value.length <= 2048 && /^\/app(?:[?#]|$)/.test(value) && !/[\\\s\p{Cc}]/u.test(value) ? value : '/app'
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    try {
      if (!auth.user && auth.resumeAfterLogin && returnTo !== '/app') sessionStorage.setItem(RETURN_KEY, returnTo)
      else sessionStorage.removeItem(RETURN_KEY)
    } catch { /* 탭 저장소를 막아도 현재 화면의 복귀 주소는 유지한다. */ }
  }, [auth.user, auth.loading, auth.resumeAfterLogin, returnTo, error])
  const [google, setGoogle] = useState(false)
  const [demo, setDemo] = useState(false)
  const finishingGoogle = params.get('google') === 'finish'
  const [googleEmail, setGoogleEmail] = useState<string | null>(null)
  const [onboardingError, setOnboardingError] = useState<unknown>(null)
  useEffect(() => {
    let current = true
    setGoogleEmail(null); setOnboardingError(null)
    if (finishingGoogle) getGoogleOnboarding().then(({ email }) => { if (current) setGoogleEmail(email) }).catch(reason => { if (current) setOnboardingError(reason) })
    return () => { current = false }
  }, [finishingGoogle])
  useEffect(() => {
    let current = true
    // 확인에 실패하면 Google 버튼을 숨기고 이메일 로그인만 보인다.
    getGoogleStatus().then(({ enabled }) => { if (current) setGoogle(enabled) }).catch(() => {})
    // 키 없는 데모(DEMO_MODE=1)에서만 서버가 답한다. 서비스에서는 404라 버튼이 생기지 않는다.
    getDemoStatus().then(({ enabled }) => { if (current) setDemo(enabled) }).catch(() => {})
    return () => { current = false }
  }, [])
  async function run(job: () => Promise<void>) {
    if (busy) return
    setBusy(true); setError(null)
    try { await job() } catch (reason) { setError(reason) } finally { setBusy(false) }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (finishingGoogle && !googleEmail) return
    const form = event.currentTarget
    const data = new FormData(form)
    const email = String(data.get('email') ?? ''), password = String(data.get('password') ?? '')
    void run(async () => {
      try { if (finishingGoogle) await auth.googleLink(email, password); else await auth.login(email, password) }
      finally { const field = form.elements.namedItem('password'); if (field instanceof HTMLInputElement) field.value = '' }
    })
  }
  if (auth.loading) return <p role="status">로그인 상태 확인 중입니다.</p>
  if (auth.user) return <Navigate to={auth.resumeAfterLogin ? returnTo : '/app'} replace />
  const failure = error || auth.error
  const credentialsFailed = (failure as Partial<ApiError> | null)?.code === 'UNAUTHORIZED'
  return <AuthCard title="로그인" links={<><Link to="/signup">회원가입</Link><Link to="/reset-password">비밀번호 재설정</Link><Link to="/privacy">개인정보처리방침</Link></>}>
    {auth.accountDeleted && <p className="notice" role="status">계정 삭제가 완료되었습니다. 탈퇴한 계정으로는 로그인할 수 없습니다. 다시 이용하려면 회원가입으로 새로 가입해 주세요.</p>}
    {demo && <div className="login-demo" role="group" aria-label="데모 로그인"><p className="login-lead">데모 모드: 비밀번호 없이 로컬 데모 전용 계정으로 들어갑니다. A와 B는 서로 다른 사용자입니다.</p>
      {(['a', 'b'] as DemoAccount[]).map(account => <button key={account} type="button" className="btn btn-large" disabled={busy} onClick={() => void run(() => auth.demoLogin(account))}>데모 사용자 {account.toUpperCase()}로 들어가기</button>)}</div>}
    {finishingGoogle && <section className="login-google" aria-label="Google 계정 확인">
      {googleEmail ? <><p className="login-lead"><strong>{googleEmail}</strong> 처음 이용한다면 Google 계정으로 가입하세요. 기존 일반 계정이 있다면 아래에서 이메일과 비밀번호를 확인해 연결하세요. 관리자 연결은 운영자 승인이 필요합니다.</p>
        <button type="button" className="btn btn-large" disabled={busy} onClick={() => void run(() => auth.googleSignup())}>{busy ? '처리 중' : 'Google 계정으로 가입'}</button></>
        : onboardingError ? <div className="notice" role="alert"><p {...requestIdProps(onboardingError)}>{errorMessage(onboardingError)}</p><a className="btn" href="/api/auth/google/start">Google 인증 다시 시작</a></div>
          : <p className="login-lead" role="status">Google 계정 확인 중입니다.</p>}
    </section>}
    {google && !finishingGoogle && <><form method="get" action="/api/auth/google/start"><button className="btn btn-large" disabled={busy}>Google 계정으로 계속</button></form><p className="login-or">또는</p></>}
    <form onSubmit={submit}>
      <label className="field"><span>이메일</span><input className="input" name="email" type="email" autoComplete="username" required maxLength={100} autoFocus /></label>
      <label className="field"><span>비밀번호</span><input className="input" name="password" type="password" autoComplete="current-password" required maxLength={1024} aria-describedby={failure ? 'login-error' : undefined} /></label>
      {failure ? <div className="notice" role="alert" id="login-error"><p {...requestIdProps(failure)}>{loginErrorMessage(failure)}</p>
        {credentialsFailed && <ul className="login-tips"><li>탈퇴했거나 아직 가입하지 않았다면 회원가입이 필요합니다.</li>{google && <li>Google로 가입했다면 Google 로그인을 이용하세요.</li>}<li>반복해서 실패했다면 15분 뒤 다시 시도해 주세요.</li></ul>}</div>
        : params.get('google') === 'error' ? <p className="notice" role="alert">Google 로그인을 확인할 수 없습니다. 계정 선택이나 동의를 취소했다면 Google 로그인을 다시 시작하세요.</p> : null}
      <button className="btn btn-primary btn-large" disabled={busy || (finishingGoogle && !googleEmail)}>{busy ? '로그인 확인 중' : finishingGoogle ? '기존 계정에 연결' : '로그인'}</button>
    </form>
  </AuthCard>
}
