import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../api/client'
import { deleteProfile, getProfile, JOB_ROLES, MOUNTING, updateProfile } from '../api/profile'
import type { ProfileChanges, ProfileKind } from '../api/profile'
import { useAuth } from '../auth/AuthProvider'
import PageShell from '../components/PageShell'

const LABELS: Record<ProfileKind, string> = { affiliation: '소속', job_role: '직무', mounting_preference: '선호 실장 방식' }
const EMPTY: Record<ProfileKind, string> = { affiliation: '', job_role: '', mounting_preference: '' }

// 다음 대화에서도 참고할 사실 3칸을 저장 · 수정 · 삭제한다(SPEC 8.5). 일반 계정은 여기서 탈퇴한다.
export default function SettingsPage() {
  const client = useQueryClient()
  const auth = useAuth()
  const facts = useQuery({ queryKey: ['profile-memory'], queryFn: ({ signal }) => getProfile(signal), retry: false, gcTime: 0 })
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [confirmAll, setConfirmAll] = useState(false)
  const [confirmLeave, setConfirmLeave] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [leaveError, setLeaveError] = useState<unknown>(null)
  const saved = { ...EMPTY, ...Object.fromEntries((facts.data ?? []).map(fact => [fact.kind, fact.value])) } as Record<ProfileKind, string>
  useEffect(() => { if (facts.data) setForm({ ...EMPTY, ...Object.fromEntries(facts.data.map(fact => [fact.kind, fact.value])) }) }, [facts.data])

  async function act(work: () => Promise<unknown>, done: string) {
    if (busy) return
    setBusy(true); setError(null); setNotice('')
    try { await work(); setNotice(done); await client.invalidateQueries({ queryKey: ['profile-memory'] }) }
    catch (reason) { setError(reason) } finally { setBusy(false) }
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
  async function leave() {
    if (busy) return
    setBusy(true); setLeaveError(null)
    // 성공하면 로그인 상태가 사라져 보호 화면이 로그인으로 보낸다.
    try { await auth.deleteAccount() } catch (reason) { setLeaveError(reason); setBusy(false) }
  }
  const select = (kind: ProfileKind, options: Record<string, string>) => <label className="field"><span>{LABELS[kind]}</span>
    <select className="input" value={form[kind]} disabled={busy} onChange={event => setForm(current => ({ ...current, [kind]: event.target.value }))}>
      <option value="">선택 안 함</option>{Object.entries(options).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
  return <PageShell title="내 설정" lead={auth.user?.email}>
    <section className="page-section" aria-labelledby="profile-heading"><h2 id="profile-heading">프로필 정보</h2>
      <p className="page-note">저장하면 다음 검토에서 참고 정보로 함께 보입니다.</p>
      {facts.isPending && <div className="skeleton" role="status"><span className="sr-only">설정을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
      {facts.error ? <div className="notice" role="alert"><p>설정을 불러오지 못했습니다. {errorMessage(facts.error)}</p><button className="btn" onClick={() => void facts.refetch()}>다시 불러오기</button></div> : null}
      <form className="form-grid" onSubmit={event => { event.preventDefault(); save() }}>
        <label className="field"><span>{LABELS.affiliation}</span><input className="input" maxLength={100} value={form.affiliation} disabled={busy} placeholder="예: 한빛전자 회로팀" onChange={event => setForm(current => ({ ...current, affiliation: event.target.value }))} /></label>
        {select('job_role', JOB_ROLES)}{select('mounting_preference', MOUNTING)}
        <div className="form-actions"><button className="btn btn-primary" disabled={busy || facts.isPending}>저장</button>{notice && <span role="status">{notice}</span>}</div>
      </form>
      {error ? <p className="notice" role="alert">{errorMessage(error)}</p> : null}
      {(facts.data ?? []).length > 0 && <><h3>저장된 설정</h3>
        <ul className="fact-list">{facts.data!.map(fact => <li key={fact.kind}><span>{fact.text}</span>
          <button type="button" className="btn" disabled={busy} onClick={() => void act(() => deleteProfile(fact.kind), `${LABELS[fact.kind]} 항목을 지웠습니다.`)}>{LABELS[fact.kind]} 지우기</button></li>)}</ul>
        {confirmAll ? <div className="confirm" role="group" aria-label="모두 지우기 확인"><p>저장한 설정을 모두 지울까요? 되돌릴 수 없습니다.</p>
          <button type="button" className="btn" disabled={busy} onClick={() => void act(async () => { await deleteProfile(); setConfirmAll(false) }, '모두 지웠습니다.')}>지우기 확인</button>
          <button type="button" className="btn" disabled={busy} onClick={() => setConfirmAll(false)}>취소</button></div>
          : <button type="button" className="btn form-start" disabled={busy} onClick={() => setConfirmAll(true)}>모두 지우기</button>}</>}
    </section>
    {auth.user?.role === 'user' && <section className="page-section" aria-labelledby="leave-heading"><h2 id="leave-heading">계정 삭제</h2>
      <p className="page-note">프로젝트, 대화, 분석 기록, 내 설정과 계정을 바로 지웁니다. 되돌릴 수 없습니다. 분석이 진행 중이면 끝난 뒤 다시 시도하세요.</p>
      {confirmLeave ? <div className="confirm" role="group" aria-label="계정 삭제 확인"><p>계정과 모든 기록을 지울까요?</p>
        <button type="button" className="btn" disabled={busy} onClick={() => void leave()}>계정 삭제 확인</button>
        <button type="button" className="btn" disabled={busy} onClick={() => setConfirmLeave(false)}>취소</button></div>
        : <button type="button" className="btn form-start" disabled={busy} onClick={() => setConfirmLeave(true)}>계정 삭제</button>}
      {leaveError ? <p className="notice" role="alert">계정을 삭제하지 못했습니다. {errorMessage(leaveError)}</p> : null}
    </section>}
  </PageShell>
}
