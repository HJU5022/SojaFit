import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteProfile, getProfile, JOB_ROLES, MOUNTING, updateProfile } from '../api/profile'
import type { ProfileChanges, ProfileKind } from '../api/profile'
import { errorMessage } from '../api/client'

const LABELS: Record<ProfileKind, string> = { affiliation: '소속', job_role: '직무', mounting_preference: '선호 실장 방식' }
const EMPTY: Record<ProfileKind, string> = { affiliation: '', job_role: '', mounting_preference: '' }

// 내 설정: 다음 대화에서도 참고로 보일 사실 3칸을 저장 · 수정 · 삭제한다(SPEC 8.5).
export default function SettingsPage() {
  const client = useQueryClient()
  const facts = useQuery({ queryKey: ['profile-memory'], queryFn: ({ signal }) => getProfile(signal), retry: false, gcTime: 0 })
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [confirmAll, setConfirmAll] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState<unknown>(null)
  const saved = { ...EMPTY, ...Object.fromEntries((facts.data ?? []).map(fact => [fact.kind, fact.value])) } as Record<ProfileKind, string>
  useEffect(() => { if (facts.data) setForm({ ...EMPTY, ...Object.fromEntries(facts.data.map(fact => [fact.kind, fact.value])) }) }, [facts.data])

  async function act(work: () => Promise<unknown>, done: string) {
    if (busy) return
    setBusy(true); setError(null); setNotice('')
    try { await work(); setNotice(done); await client.invalidateQueries({ queryKey: ['profile-memory'] }) }
    catch (error) { setError(error) }
    finally { setBusy(false) }
  }
  function save() {
    // 바뀐 칸만 보낸다. 빈 칸은 지우기 버튼으로만 지운다.
    const changes: ProfileChanges = {}
    for (const kind of Object.keys(LABELS) as ProfileKind[]) {
      const value = kind === 'affiliation' ? form[kind].trim() : form[kind]
      if (value && value !== saved[kind]) changes[kind] = value
    }
    if (Object.keys(changes).length === 0) { setNotice('바뀐 칸이 없습니다.'); return }
    void act(() => updateProfile(changes), '저장했습니다.')
  }
  const select = (kind: ProfileKind, options: Record<string, string>) => <select id={`profile-${kind}`} value={form[kind]} disabled={busy}
    onChange={event => setForm(current => ({ ...current, [kind]: event.target.value }))}>
    <option value="">선택 안 함</option>{Object.entries(options).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
  </select>
  return <><h1>내 설정</h1>
    <p>여기 적은 사실은 다음 대화에서도 답 옆에 참고(내 설정)로 보입니다. 판정 근거로 쓰지 않으며, 전압 · 전류 같은 회로 값과 승인한 판정은 저장하지 않습니다.</p>
    <section className="panel" aria-labelledby="profile-heading"><h2 id="profile-heading">사실 3칸</h2>
      {facts.isPending && <p role="status">설정을 불러오는 중입니다.</p>}
      {facts.error ? <p role="alert">{errorMessage(facts.error)}</p> : null}
      <form onSubmit={event => { event.preventDefault(); save() }}>
        <label htmlFor="profile-affiliation">{LABELS.affiliation}</label>
        <input id="profile-affiliation" maxLength={100} value={form.affiliation} disabled={busy} placeholder="예: 한빛전자 회로팀"
          onChange={event => setForm(current => ({ ...current, affiliation: event.target.value }))} />
        <label htmlFor="profile-job_role">{LABELS.job_role}</label>{select('job_role', JOB_ROLES)}
        <label htmlFor="profile-mounting_preference">{LABELS.mounting_preference}</label>{select('mounting_preference', MOUNTING)}
        <button type="submit" disabled={busy || facts.isPending}>저장</button>
      </form>
      {(facts.data ?? []).length > 0 && <ul className="profile-facts">{facts.data!.map(fact => <li key={fact.kind}>
        <span>{fact.text}</span> <button type="button" className="secondary" disabled={busy}
          onClick={() => void act(() => deleteProfile(fact.kind), `${LABELS[fact.kind]}을(를) 지웠습니다.`)}>{LABELS[fact.kind]} 지우기</button>
      </li>)}</ul>}
      {(facts.data ?? []).length > 0 && !confirmAll && <button type="button" className="secondary" disabled={busy} onClick={() => setConfirmAll(true)}>모두 지우기</button>}
      {confirmAll && <div role="group" aria-label="모두 지우기 확인"><p>저장한 사실 3칸을 모두 지울까요? 되돌릴 수 없습니다.</p>
        <button type="button" disabled={busy} onClick={() => void act(async () => { await deleteProfile(); setConfirmAll(false) }, '모두 지웠습니다.')}>지우기 확인</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => setConfirmAll(false)}>취소</button></div>}
      {notice && <p role="status">{notice}</p>}
      {error ? <p role="alert">{errorMessage(error)}</p> : null}
    </section>
  </>
}
