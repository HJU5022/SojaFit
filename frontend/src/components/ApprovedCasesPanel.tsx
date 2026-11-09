import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteApprovedCase, listApprovedCases } from '../api/quotes'
import { errorMessage } from '../api/client'

export default function ApprovedCasesPanel() {
  const client = useQueryClient()
  const cases = useQuery({ queryKey: ['approved-cases'], queryFn: ({ signal }) => listApprovedCases(signal), retry: false, gcTime: 0 })
  const [confirm, setConfirm] = useState<number | null>(null)
  const remove = useMutation({ mutationFn: (id: number) => deleteApprovedCase(id), onSuccess: () => { setConfirm(null); void client.invalidateQueries({ queryKey: ['approved-cases'] }) } })
  const items = Array.isArray(cases.data) ? cases.data : []
  return <section className="panel result-section" aria-labelledby="cases-heading"><h2 id="cases-heading">승인 사례</h2>
    {cases.isPending && <p role="status">승인 사례를 불러오는 중입니다.</p>}
    {cases.error && <p role="alert">{errorMessage(cases.error)}</p>}
    {!cases.isPending && items.length === 0 && <p>저장된 승인 사례가 없습니다.</p>}
    <ul className="case-list">{items.map(item => <li key={item.id}><span>{item.candidate_part} · {item.verdict}</span>
      <button className="secondary" onClick={() => setConfirm(item.id)}>사례 삭제</button>
      {confirm === item.id && <div role="group" aria-label={`${item.candidate_part} 사례 삭제 확인`}><p>이 승인 사례를 삭제할까요?</p>
        <button className="danger" disabled={remove.isPending} onClick={() => remove.mutate(item.id)}>삭제 확인</button>
        <button className="secondary" disabled={remove.isPending} onClick={() => setConfirm(null)}>취소</button></div>}</li>)}</ul>
    {remove.error && <p role="alert">{errorMessage(remove.error)}</p>}
  </section>
}
