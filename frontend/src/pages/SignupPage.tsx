import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthProvider'

// 가입: 이메일 · 8자 이상 비밀번호 · 처리방침 고지 동의(필수). 동의 없이는 보내지 않고, 서버도 consent가 없으면 422다(SPEC 4절 · 8.6)
export default function SignupPage() {
  const auth = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const ready = agreed && password.length >= 8
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || !ready) return
    setBusy(true); setError(null)
    try { await auth.signup(email, password) } catch (error) { setError(error) }
    finally { setPassword(''); setBusy(false) }
  }
  if (auth.loading) return <p role="status">로그인 상태 확인 중입니다.</p>
  if (auth.user) return <Navigate to="/app" replace />
  return <section className="panel login-panel">
    <h1>가입</h1><p>로컬 데모 전용 가입입니다. 이메일 인증은 하지 않습니다. 배포 서비스는 로그인 화면의 Google로 가입합니다.</p>
    <form onSubmit={(event) => void submit(event)}>
      <label htmlFor="signup-email">이메일</label>
      <input id="signup-email" type="email" autoComplete="username" required maxLength={100} value={email} onChange={(event) => setEmail(event.target.value)} />
      <label htmlFor="signup-password">비밀번호(8자 이상)</label>
      <input id="signup-password" type="password" autoComplete="new-password" required minLength={8} maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} />
      <PrivacyNotice />
      <label className="consent"><input type="checkbox" required checked={agreed} onChange={(event) => setAgreed(event.target.checked)} />
        위 안내를 읽었고 개인정보 수집 · 이용에 동의합니다(필수)</label>
      <button disabled={busy || !ready} type="submit">{busy ? '가입 중…' : '가입'}</button>
    </form>
    {error ? <p role="alert">{errorMessage(error)}</p> : null}
    <p>이미 계정이 있으면 <Link to="/login">로그인</Link></p>
  </section>
}

// 가입 전에 알리는 처리방침 요약(개인정보 보호법 15조 2항). 바꾸면 docs/specs/user-thread-memory.md "보관 · 삭제"와 맞춘다
export function PrivacyNotice() {
  return <section className="privacy-notice" aria-labelledby="privacy-heading">
    <h2 id="privacy-heading">개인정보 처리 안내</h2>
    <ul>
      <li>쓰는 목적: 회로의 대체 부품 판정 서비스 제공과 계정 · 사용량 관리.</li>
      <li>저장하는 것: 계정(이메일, 비밀번호는 해시로만 · Google로 가입하면 이메일과 Google 계정 식별자만, 비밀번호 없음), 회로 · 대화(프로젝트와 분석 기록), 내 설정 3칸(소속 · 직무 · 선호 실장 방식).</li>
      <li>보관 기간: 프로젝트는 마지막 활동 뒤 60일, 기록(분석 사건 · 로그인 시도 · 하루 사용량)은 30일이 지나면 자동으로 지웁니다. 내 설정은 직접 지울 때까지 둡니다.</li>
      <li>삭제: 프로젝트 삭제와 계정 삭제(내 설정 화면)는 숨기지 않고 바로 지웁니다.</li>
      <li>분석 추적: Langfuse로 보내는 분석 기록에는 질문 · 답변 글을 넣지 않습니다.</li>
      <li>외부 서비스: 위 정보는 서비스 데이터베이스에 저장하고, 질문 · 회로는 OpenRouter(LLM), 검색 질문 · 소속 글은 Voyage(임베딩)로 보냅니다.</li>
      <li>동의를 거부할 수 있으며, 거부하면 가입할 수 없습니다.</li>
    </ul>
  </section>
}
