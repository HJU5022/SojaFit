import { useState } from 'react'
import type { InterruptDto } from '../api/conversations'

export default function InterruptForm({ interrupt, busy, onSubmit }: { interrupt: InterruptDto; busy: boolean; onSubmit: (answers: Record<string, string>, role?: string) => void }) {
  const missing = interrupt.missing ?? []
  const roles = interrupt.role_choices ?? []
  const [answers, setAnswers] = useState<Record<string, string>>(() => Object.fromEntries(missing.map(key => [key, ''])))
  const [role, setRole] = useState('')
  const complete = missing.every(key => answers[key]?.trim()) && (roles.length === 0 || roles.includes(role))
  return <form className="interrupt-form" onSubmit={event => { event.preventDefault(); if (complete) onSubmit(answers, role || undefined) }}>
    <h3>추가 정보</h3><p>{interrupt.question || '판정에 필요한 값을 알려 주세요.'}</p>
    {roles.length > 0 && <><label htmlFor="interrupt-role">회로 역할</label><select id="interrupt-role" value={role} onChange={event => setRole(event.target.value)} disabled={busy}>
      <option value="">역할을 선택하세요</option>{roles.map(item => <option key={item} value={item}>{item}</option>)}
    </select></>}
    {missing.map(key => <div key={key}><label htmlFor={`interrupt-${key}`}>{key}</label><input id={`interrupt-${key}`} value={answers[key] ?? ''} maxLength={200} disabled={busy}
      onChange={event => setAnswers(current => ({ ...current, [key]: event.target.value }))} /></div>)}
    <button disabled={busy || !complete}>같은 실행 계속하기</button>
  </form>
}
