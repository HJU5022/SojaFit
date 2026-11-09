import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ApprovalDto, QuoteDto } from '../api/quotes'
import { createQuote } from '../api/quotes'
import { errorMessage } from '../api/client'
import { getProfile } from '../api/profile'
import PricePanel from './PricePanel'

export default function QuotePanel({ approval }: { approval: ApprovalDto | null }) {
  const [open, setOpen] = useState(false)
  const [quantity, setQuantity] = useState(1)
  const [saved, setSaved] = useState<QuoteDto | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  // 견적 머리의 소속은 내 설정에서 읽는다. 못 읽으면 소속 줄만 비운다
  const profile = useQuery({ queryKey: ['profile-memory'], queryFn: ({ signal }) => getProfile(signal), enabled: open, retry: false, gcTime: 0 })
  const affiliation = profile.data?.find(fact => fact.kind === 'affiliation')?.value
  async function save() {
    if (!approval || busy) return
    setBusy(true); setError(null)
    try { setSaved(await createQuote(approval.id, quantity)) } catch (error) { setError(error) } finally { setBusy(false) }
  }
  return <div className="quote-panel"><button className="secondary" disabled={!approval} onClick={() => setOpen(value => !value)}>견적 열기</button>
    {open && approval && <div><header className="quote-header"><h3>견적</h3>{affiliation && <p>소속: {affiliation}</p>}</header>
      <PricePanel parts={[approval.candidate_part]} />
      <label htmlFor="quote-quantity">수량</label><input id="quote-quantity" type="number" min={1} max={100000} value={quantity} onChange={event => setQuantity(Number(event.target.value))} />
      <button disabled={busy || quantity < 1 || quantity > 100000} onClick={() => void save()}>가격 없이 견적 저장</button>
      {saved && <p role="status">{saved.part_number} {saved.quantity}개 견적을 저장했습니다. 가격은 저장하지 않았습니다.</p>}
      {error ? <p role="alert">{errorMessage(error)}</p> : null}
    </div>}
  </div>
}
