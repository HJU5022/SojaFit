import '@fontsource-variable/noto-sans-kr'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { completeSignup, completePasswordReset, requestPasswordReset, newPasswordIssue } from '../api/auth'
import { errorMessage } from '../api/client'

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
      if (window.location.hash) window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search)
    }
    receiveLink()
    window.addEventListener('hashchange', receiveLink)
    return () => { actionVersion.current += 1; window.removeEventListener('hashchange', receiveLink) }
  }, [])
  const validToken = /^[A-Za-z0-9_-]{43}$/.test(token)
  const passwordIssue = newPasswordIssue(password)
  const showPasswordIssue = password.length > 0 && !!passwordIssue
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
      if (purpose === 'reset') {
        window.dispatchEvent(new Event('sojafit:session-expired'))
      }
      setToken(''); setDone(true)
    } catch (error) { if (version === actionVersion.current) setError(error) }
    finally { if (version === actionVersion.current) { setPassword(''); setConfirmation(''); setBusy(false) } }
  }
  async function request(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    const version = actionVersion.current
    setBusy(true); setError(null)
    try { await requestPasswordReset(email); if (version === actionVersion.current) setSent(true) }
    catch (error) { if (version === actionVersion.current) setError(error) }
    finally { if (version === actionVersion.current) setBusy(false) }
  }
  const title = purpose === 'signup' ? '이메일 인증 및 비밀번호 설정' : validToken ? '새 비밀번호 설정' : '비밀번호 재설정'
  return <div className="public-site login-page signup-page email-action-page">
    <header className="public-header"><Link className="public-brand" to="/"><img className="brand-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT" width="174" height="48" /></Link><Link to="/login">로그인</Link></header>
    <div className="public-auth-grid">
      <aside className="public-auth-story"><h2>내 계정을<br />안전하게 관리하세요.</h2><p>이메일로 받은 링크는 한 번만 사용할 수 있습니다. 비밀번호나 인증 링크를 다른 사람에게 보내지 마세요.</p></aside>
      <section className="public-auth-form"><div className="public-auth-content">
        <h1>{title}</h1>
        {!done && validToken && <p className="email-action-intro">{purpose === 'signup' ? '사용할 비밀번호를 설정하면 가입이 완료됩니다.' : '다른 곳에서 사용하지 않는 비밀번호로 설정해 주세요.'}</p>}
        {done ? <p role="status">{purpose === 'signup' ? '가입이 완료되었습니다. 로그인해 주세요.' : '비밀번호가 변경되었습니다. 기존 로그인은 해제되었으니 다시 로그인해 주세요.'}</p>
          : validToken ? <form onSubmit={event => void submit(event)}>
            <label htmlFor="new-password">새 비밀번호(12자 이상)</label>
            <input id="new-password" type="password" autoComplete="new-password" required minLength={12} maxLength={2048} aria-invalid={showPasswordIssue || undefined} aria-describedby={showPasswordIssue ? 'new-password-policy' : undefined} value={password} onChange={event => setPassword(event.target.value)} />
            <p id="new-password-policy" className="email-action-password-issue" role="status">{showPasswordIssue ? passwordIssue : ''}</p>
            <label htmlFor="confirm-password">새 비밀번호 확인</label>
            <input id="confirm-password" type="password" autoComplete="new-password" required maxLength={2048} aria-invalid={confirmation && password !== confirmation ? true : undefined} aria-describedby={confirmation && password !== confirmation ? 'password-mismatch' : undefined} value={confirmation} onChange={event => setConfirmation(event.target.value)} />
            {confirmation && password !== confirmation && <p id="password-mismatch" className="email-action-mismatch" role="status">비밀번호가 일치하지 않습니다.</p>}
            <button type="submit" disabled={busy || !ready}>{busy ? '처리 중…' : purpose === 'signup' ? '인증하고 가입 완료' : '비밀번호 변경'}</button>
          </form> : token || purpose === 'signup' ? <div><p role="alert">유효한 메일 링크가 없습니다. 이메일을 다시 요청해 주세요.</p>{purpose === 'signup' ? <Link to="/signup">인증 메일 다시 요청</Link> : <button onClick={() => { setToken(''); setError(null) }}>재설정 메일 다시 요청</button>}</div>
            : <form onSubmit={event => void request(event)}>
              <p>비밀번호로 가입한 계정의 이메일을 입력하세요. Google로만 가입했다면 Google 로그인을 이용해 주세요.</p>
              <label htmlFor="reset-email">이메일</label>
              <input id="reset-email" type="email" autoComplete="username" required maxLength={100} value={email} onChange={event => setEmail(event.target.value)} />
              <button type="submit" disabled={busy}>{busy ? '요청 중…' : '재설정 메일 요청'}</button>
            </form>}
        {sent && <p role="status">재설정 가능한 계정이라면 안내 메일을 보냈습니다. 스팸함도 확인해 주세요. 재요청은 60초 뒤 가능합니다.</p>}
        {error ? <p role="alert">{errorMessage(error)}</p> : null}
        <footer className="email-action-links"><Link to="/login">로그인 화면으로</Link><Link to="/privacy">개인정보처리방침</Link></footer>
      </div></section>
    </div>
  </div>
}
