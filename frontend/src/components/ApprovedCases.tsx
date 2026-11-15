import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { errorMessage, requestIdProps } from '../api/client'
import type { CandidateDto } from '../api/conversations'
import { deleteApprovedCase, listApprovedCases } from '../api/quotes'
import { VERDICT_LABELS, VERDICT_TONE } from '../lib/judgement'

// 사람이 승인한 판정 목록. 창이 열릴 때마다 새로 읽는다.
export default function ApprovedCases() {
  const client = useQueryClient()
  const cases = useQuery({ queryKey: ['approved-cases'], queryFn: ({ signal }) => listApprovedCases(signal), retry: false, gcTime: 0 })
  const [confirm, setConfirm] = useState<number | null>(null)
  const remove = useMutation({ mutationFn: (id: number) => deleteApprovedCase(id), onSuccess: () => setConfirm(null), onSettled: async () => {
    await Promise.all([client.invalidateQueries({ queryKey: ['approved-cases'] }), client.invalidateQueries({ queryKey: ['message-approvals'] })])
  } })
  const items = Array.isArray(cases.data) ? cases.data : []
  if (cases.isPending) return <div className="skeleton" role="status"><span className="sr-only">승인 사례를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>
  if (cases.error) return <div className="notice" role="alert"><p {...requestIdProps(cases.error)}>승인 사례를 불러오지 못했습니다. {errorMessage(cases.error)}</p><button type="button" className="btn" onClick={() => void cases.refetch()}>다시 불러오기</button></div>
  if (!items.length) return <p className="empty">저장된 승인 사례가 없습니다. 검토 결과에서 검토하고 승인을 누르면 여기에 쌓입니다.</p>
  return <>
    <ul className="fact-list">{items.map(item => {
      const verdict = item.verdict as CandidateDto['verdict']
      return <li key={item.id}><span><strong>{item.candidate_part}</strong><span className={`dot tone-${VERDICT_TONE[verdict] ?? 'unverified'}`}>{VERDICT_LABELS[verdict] ?? '판정 없음'}</span></span>
        {confirm === item.id ? <span className="row-actions"><span className="property-note">승인을 취소하고 사례를 삭제합니다. 기존 견적은 이력으로 남습니다.</span><button type="button" className="btn" disabled={remove.isPending} onClick={() => remove.mutate(item.id)}>삭제 확인</button><button type="button" className="btn" disabled={remove.isPending} onClick={() => setConfirm(null)}>취소</button></span>
          : <button type="button" className="btn" aria-label={`${item.candidate_part} 사례 삭제`} onClick={() => setConfirm(item.id)}>삭제</button>}</li>
    })}</ul>
    {remove.error ? <p className="notice" role="alert" {...requestIdProps(remove.error)}>사례를 삭제하지 못했습니다. {errorMessage(remove.error)}</p> : null}
  </>
}
