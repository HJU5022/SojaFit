import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { completePasswordReset, completeSignup, newPasswordIssue, requestPasswordReset } from '../api/auth'
import { errorMessage, requestIdProps } from '../api/client'
import AuthCard from '../components/AuthCard'

// 메일 링크(#token=)로 들어와 비밀번호를 정한다. 가입 완료와 비밀번호 재설정이 같은 흐름이다.
export default function EmailActionPage({ purpose }: { purpose: 'signup' | 'reset' }) {
  const [token, setToken] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') ?? '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const actionVersion = useRef(0)
  useEffect(() => {
    function receiveLink() {
      const incoming = new URLSearchParams(window.location.hash.slice(1)).get('token')
      if (incoming !== null) {
        actionVersion.current += 1
        setToken(incoming); setDone(false); setSent(false); setError(null)
        setPassword(''); setConfirmation(''); setBusy(false)
      }
      // 토큰이 주소와 방문 기록에 남지 않게 지운다.
      if (window.location.hash) window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search)
    }
    receiveLink()
    window.addEventListener('hashchange', receiveLink)
    return () => { actionVersion.current += 1; window.removeEventListener('hashchange', receiveLink) }
  }, [])
  const validToken = /^[A-Za-z0-9_-]{43}$/.test(token)
  const passwordIssue = newPasswordIssue(password)
  const showPasswordIssue = password.length > 0 && !!passwordIssue
  const mismatch = Boolean(confirmation) && password !== confirmation
  const ready = !passwordIssue && password === confirmation
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || !validToken || !ready) return
    const version = actionVersion.current
    setBusy(true); setError(null)
    try {
      if (purpose === 'signup') await completeSignup(token, password)
      else await completePasswordReset(token, password)
      if (version !== actionVersion.current) return
      if (purpose === 'reset') window.dispatchEvent(new Event('sojafit:session-expired'))
      setToken(''); setDone(true)
    } catch (reason) { if (version === actionVersion.current) setError(reason) }
    finally { if (version === actionVersion.current) { setPassword(''); setConfirmation(''); setBusy(false) } }
  }
  async function request(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    const version = actionVersion.current
    setBusy(true); setError(null)
    try { await requestPasswordReset(email); if (version === actionVersion.current) setSent(true) }
    catch (reason) { if (version === actionVersion.current) setError(reason) }
    finally { if (version === actionVersion.current) setBusy(false) }
  }
  const title = purpose === 'signup' ? '이메일 인증 및 비밀번호 설정' : validToken ? '새 비밀번호 설정' : '비밀번호 재설정'
  const lead = done || !validToken ? undefined : purpose === 'signup' ? '사용할 비밀번호를 설정하면 가입이 완료됩니다.' : '다른 곳에서 사용하지 않는 비밀번호로 설정해 주세요.'
  return <AuthCard title={title} lead={lead} links={<><Link to="/login">로그인</Link><Link to="/privacy">개인정보처리방침</Link></>}>
    {done ? <p className="notice" role="status">{purpose === 'signup' ? '가입이 완료되었습니다. 로그인해 주세요.' : '비밀번호가 변경되었습니다. 기존 로그인은 해제되었으니 다시 로그인해 주세요.'}</p>
      : validToken ? <form onSubmit={event => void submit(event)}>
        <label className="field"><span>새 비밀번호(12자 이상)</span><input className="input" type="password" autoComplete="new-password" required minLength={12} maxLength={2048} autoFocus aria-invalid={showPasswordIssue || undefined} aria-describedby="new-password-policy" value={password} onChange={event => setPassword(event.target.value)} />
          <span id="new-password-policy" className="field-hint" role="status">{showPasswordIssue ? passwordIssue : ''}</span></label>
        <label className="field"><span>새 비밀번호 확인</span><input className="input" type="password" autoComplete="new-password" required maxLength={2048} aria-invalid={mismatch || undefined} aria-describedby="password-mismatch" value={confirmation} onChange={event => setConfirmation(event.target.value)} />
          <span id="password-mismatch" className="field-hint" role="status">{mismatch ? '비밀번호가 일치하지 않습니다.' : ''}</span></label>
        <button className="btn btn-primary btn-large" disabled={busy || !ready}>{busy ? '처리 중' : purpose === 'signup' ? '인증하고 가입 완료' : '비밀번호 변경'}</button>
      </form>
        : token || purpose === 'signup' ? <div className="notice" role="alert"><p>유효한 메일 링크가 없습니다. 이메일을 다시 요청해 주세요.</p>
          {purpose === 'signup' ? <Link className="btn" to="/signup">인증 메일 다시 요청</Link> : <button className="btn" onClick={() => { setToken(''); setError(null) }}>재설정 메일 다시 요청</button>}</div>
          : <form onSubmit={event => void request(event)}>
            <p className="login-lead">비밀번호로 가입한 계정의 이메일을 입력하세요. Google로만 가입했다면 Google 로그인을 이용해 주세요.</p>
            <label className="field"><span>이메일</span><input className="input" type="email" autoComplete="username" required maxLength={100} autoFocus value={email} onChange={event => setEmail(event.target.value)} /></label>
            {sent && <p className="notice" role="status">재설정 가능한 계정이라면 안내 메일을 보냈습니다. 스팸함도 확인해 주세요. 재요청은 60초 뒤 가능합니다.</p>}
            <button className="btn btn-primary btn-large" disabled={busy}>{busy ? '요청 중' : '재설정 메일 요청'}</button>
          </form>}
    {error ? <p className="notice" role="alert" {...requestIdProps(error)}>{errorMessage(error)}</p> : null}
  </AuthCard>
}
