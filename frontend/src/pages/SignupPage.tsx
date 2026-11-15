import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { errorMessage, requestIdProps } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import AuthCard from '../components/AuthCard'

export default function SignupPage() {
  const auth = useAuth()
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const email = String(new FormData(event.currentTarget).get('email') ?? '')
    setBusy(true); setError(null)
    try { await auth.signup(email); setSent(true) } catch (reason) { setError(reason) } finally { setBusy(false) }
  }
  if (auth.loading) return <p role="status">로그인 상태 확인 중입니다.</p>
  if (auth.user) return <Navigate to="/app" replace />
  return <AuthCard title="회원가입" lead="이메일을 확인한 뒤 비밀번호를 설정해 계정을 만듭니다."
    links={<><Link to="/login">로그인</Link><Link to="/privacy">개인정보처리방침</Link></>}>
    <form onSubmit={submit} data-refresh-blocked={busy}>
      <label className="field"><span>이메일</span><input className="input" name="email" type="email" autoComplete="username" required maxLength={100} autoFocus /></label>
      {sent && <p className="notice" role="status">가입 가능한 이메일이라면 인증 메일을 보냈습니다. 스팸함도 확인해 주세요. 메일 링크에서 비밀번호를 설정해야 가입이 완료됩니다. 재요청은 60초 뒤 가능합니다.</p>}
      {error ? <p className="notice" role="alert" {...requestIdProps(error)}>{errorMessage(error)}</p> : null}
      <button className="btn btn-primary btn-large" disabled={busy}>{busy ? '요청 중' : '인증 메일 요청'}</button>
    </form>
  </AuthCard>
}
