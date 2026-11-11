import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { CandidateDto, JudgementDto } from '../api/conversations'
import { getRun } from '../api/conversations'
import type { ApprovalDto } from '../api/quotes'
import { approveMessage } from '../api/quotes'
import { errorMessage } from '../api/client'
import QuotePanel from './QuotePanel'
import { candidatesOf } from './circuitContext'
import AccessibleDialog from './AccessibleDialog'

const LABELS: Partial<Record<CandidateDto['verdict'], string>> = { IDENTICAL: '동일품', SPEC_EQUIVALENT: '사양 동등', ROLE_SUFFICIENT: '역할상 충분' }

function approvalBlocker(candidate?: CandidateDto) {
  if (!candidate) return ''
  const unverified = candidate.checks?.find(check => check.tier === 'required' && check.result === 'unverified')
  if (unverified) return unverified.why || `${unverified.code} 필수 조건을 확인하지 못했습니다.`
  if (candidate.missing?.length) return `필수 조건을 확인하지 못했습니다: ${candidate.missing.join(', ')}`
  return ''
}

export default function ApprovalPanel({ runId, judgement }: { runId?: string; judgement?: JudgementDto | Record<string, never> }) {
  const client = useQueryClient()
  // 판정 표에 보인 후보 중 승인할 수 있는 판정(동일품 · 사양 동등 · 역할상 충분)만
  const candidates = candidatesOf(judgement).filter(item => item.verdict in LABELS)
  const [candidate, setCandidate] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [approval, setApproval] = useState<ApprovalDto | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const selected = candidate === '' ? undefined : candidates[Number(candidate)]
  const blocker = approvalBlocker(selected)
  async function approve() {
    if (!runId || !selected || busy || blocker) return
    setBusy(true); setError(null)
    try {
      const run = await getRun(runId)
      if (!run.message_id) throw { code: 'APPROVAL_NOT_READY', message: '승인할 결과 메시지를 찾을 수 없습니다.', requestId: run.result.request_id }
      setApproval(await approveMessage(run.message_id, selected.part, selected.verdict)); setConfirm(false)
      void client.invalidateQueries({ queryKey: ['approved-cases'] })
    } catch (error) { setError(error) } finally { setBusy(false) }
  }
  return <section className="panel result-section" aria-labelledby="approval-heading"><h2 id="approval-heading">사람 승인</h2>
    <p>근거와 판정을 직접 확인한 뒤 승인하세요.</p>
    <label htmlFor="approval-candidate">승인할 후보</label><select id="approval-candidate" value={candidate} disabled={busy || !!approval} onChange={event => { setCandidate(event.target.value); setConfirm(false) }}>
      <option value="">후보를 선택하세요</option>{candidates.map((item, index) => <option key={`${item.part}-${item.verdict}-${index}`} value={index}>{item.part} · {LABELS[item.verdict]}</option>)}
    </select>
    <button disabled={!runId || !selected || busy || !!approval || !!blocker} onClick={() => setConfirm(true)}>판정 승인 확인</button>
    {blocker && <p role="alert">승인할 수 없습니다. {blocker}</p>}
    {confirm && selected && <AccessibleDialog title="판정 승인 확인" closeOnBackdrop={false} onClose={() => setConfirm(false)}><p>{selected.part} 후보의 “{LABELS[selected.verdict]}” 판정을 승인할까요?</p>
      <p>승인된 결과만 견적 단계로 이동합니다.</p><div className="dialog-actions"><button disabled={busy} onClick={() => void approve()}>확인 후 승인</button><button className="secondary" disabled={busy} onClick={() => setConfirm(false)}>취소</button></div></AccessibleDialog>}
    {approval && <p role="status">{approval.candidate_part} 판정을 승인했습니다.</p>}
    {error ? <p role="alert">{errorMessage(error)}</p> : null}
    <QuotePanel approval={approval} />
  </section>
}
