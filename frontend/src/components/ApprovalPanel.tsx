import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { CandidateDto, JudgementDto } from '../api/conversations'
import { getRun } from '../api/conversations'
import type { ApprovalDto } from '../api/quotes'
import { approveMessage } from '../api/quotes'
import { errorMessage } from '../api/client'
import QuotePanel from './QuotePanel'

const LABELS: Partial<Record<CandidateDto['verdict'], string>> = { IDENTICAL: '동일품', SPEC_EQUIVALENT: '사양 동등', ROLE_SUFFICIENT: '역할상 충분' }

export default function ApprovalPanel({ runId, judgement }: { runId?: string; judgement?: JudgementDto | Record<string, never> }) {
  const client = useQueryClient()
  const candidates = judgement && 'kind' in judgement ? [...judgement.results, ...judgement.shown].filter(item => item.verdict in LABELS) : []
  const [candidate, setCandidate] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [approval, setApproval] = useState<ApprovalDto | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const selected = candidates.find(item => item.part === candidate)
  async function approve() {
    if (!runId || !selected || busy) return
    setBusy(true); setError(null)
    try {
      const run = await getRun(runId)
      if (!run.message_id) throw { code: 'APPROVAL_NOT_READY', message: '승인할 결과 메시지를 찾을 수 없습니다.', requestId: run.result.request_id }
      setApproval(await approveMessage(run.message_id, selected.part)); setConfirm(false)
      void client.invalidateQueries({ queryKey: ['approved-cases'] })
    } catch (error) { setError(error) } finally { setBusy(false) }
  }
  return <section className="panel result-section" aria-labelledby="approval-heading"><h2 id="approval-heading">사람 승인</h2>
    <p>근거와 판정을 직접 확인한 뒤 승인하세요.</p>
    <label htmlFor="approval-candidate">승인할 후보</label><select id="approval-candidate" value={candidate} disabled={busy || !!approval} onChange={event => { setCandidate(event.target.value); setConfirm(false) }}>
      <option value="">후보를 선택하세요</option>{candidates.map(item => <option key={`${item.part}-${item.verdict}`} value={item.part}>{item.part} · {LABELS[item.verdict]}</option>)}
    </select>
    <button disabled={!runId || !selected || busy || !!approval} onClick={() => setConfirm(true)}>판정 승인 확인</button>
    {confirm && selected && <div role="group" aria-label="판정 승인 확인"><p>{selected.part} 후보의 “{LABELS[selected.verdict]}” 판정을 승인할까요?</p>
      <button disabled={busy} onClick={() => void approve()}>확인 후 승인</button><button className="secondary" disabled={busy} onClick={() => setConfirm(false)}>취소</button></div>}
    {approval && <p role="status">{approval.candidate_part} 판정을 승인했습니다.</p>}
    {error ? <p role="alert">{errorMessage(error)}</p> : null}
    <QuotePanel approval={approval} />
  </section>
}
