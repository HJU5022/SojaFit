import { useState } from 'react'
import type { ApprovalDto, QuoteDto } from '../api/quotes'
import { createQuote } from '../api/quotes'
import { errorMessage } from '../api/client'
import PricePanel from './PricePanel'

export default function QuotePanel({ approval }: { approval: ApprovalDto | null }) {
  const [open, setOpen] = useState(false)
  const [quantity, setQuantity] = useState(1)
  const [saved, setSaved] = useState<QuoteDto | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  async function save() {
    if (!approval || busy) return
    setBusy(true); setError(null)
    try { setSaved(await createQuote(approval.id, quantity)) } catch (error) { setError(error) } finally { setBusy(false) }
  }
  return <div className="quote-panel"><button className="secondary" disabled={!approval} onClick={() => setOpen(value => !value)}>견적 열기</button>
    {open && approval && <div><PricePanel parts={[approval.candidate_part]} />
      <label htmlFor="quote-quantity">수량</label><input id="quote-quantity" type="number" min={1} max={100000} value={quantity} onChange={event => setQuantity(Number(event.target.value))} />
      <button disabled={busy || quantity < 1 || quantity > 100000} onClick={() => void save()}>가격 없이 견적 저장</button>
      {saved && <p role="status">{saved.part_number} {saved.quantity}개 견적을 저장했습니다. 가격은 저장하지 않았습니다.</p>}
      {error ? <p role="alert">{errorMessage(error)}</p> : null}
    </div>}
  </div>
}
