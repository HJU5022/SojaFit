import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthProvider'

export default function SignupPage() {
  const auth = useAuth()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const ready = email.trim().length > 0
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || !ready) return
    setBusy(true); setError(null)
    try { await auth.signup(email); setSent(true) } catch (error) { setError(error) }
    finally { setBusy(false) }
  }
  if (auth.loading) return <p role="status">로그인 상태 확인 중입니다.</p>
  if (auth.user) return <Navigate to="/app" replace />
  return <div className="public-site login-page signup-page">
    <header className="public-header"><Link className="public-brand" to="/"><img className="brand-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT" width="174" height="48" /></Link><Link className="public-secondary" to="/">서비스 소개</Link></header>
    <div className="public-auth-grid">
      <aside className="public-auth-story"><h2>내 회로에서 시작하는<br />부품 검토.</h2><p>계정을 만들고 회로 프로젝트와 대화, 분석 근거를 한곳에서 관리하세요.</p><img className="public-auth-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT 브랜드 로고" width="920" height="256" /><p className="public-auth-caption">회로 맥락 / 후보 비교 / 문서 근거</p></aside>
      <section className="public-auth-form"><div className="public-auth-content">
    <h1>SojaFit 회원가입</h1><p>이메일을 확인한 뒤 비밀번호를 설정해 계정을 만듭니다.</p>
    <form onSubmit={(event) => void submit(event)}>
      <label htmlFor="signup-email">이메일</label>
      <input id="signup-email" type="email" autoComplete="username" required maxLength={100} value={email} onChange={(event) => setEmail(event.target.value)} />
      <button disabled={busy || !ready} type="submit">{busy ? '요청 중…' : '인증 메일 요청'}</button>
    </form>
    {sent && <p role="status">가입 가능한 이메일이라면 인증 메일을 보냈습니다. 스팸함도 확인해 주세요. 메일 링크에서 비밀번호를 설정해야 가입이 완료됩니다. 재요청은 60초 뒤 가능합니다.</p>}
    {error ? <p role="alert">{errorMessage(error)}</p> : null}
    <p>이미 계정이 있으면 <Link to="/login">로그인</Link></p>
    <p className="public-legal"><Link to="/privacy">개인정보처리방침</Link></p>
    </div></section></div>
  </div>
}
