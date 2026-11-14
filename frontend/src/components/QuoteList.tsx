import { useQuery } from '@tanstack/react-query'
import { errorMessage, requestIdProps } from '../api/client'
import { getThread } from '../api/conversations'
import { listQuotes } from '../api/quotes'
import PriceLookup from './PriceLookup'

// 프로젝트의 견적 목록: 품번 × 수량과 만든 날만 서버에서 읽는다. 가격은 행마다 누를 때 실시간으로 조회한다(저장하지 않음).
export default function QuoteList({ projectId, onOpen }: { projectId: number; onOpen: (threadId: string, targetRef?: string) => void }) {
  const quotes = useQuery({ queryKey: ['quotes', projectId], queryFn: ({ signal }) => listQuotes(projectId, signal), retry: false, gcTime: 0 })
  const items = Array.isArray(quotes.data) ? quotes.data : []
  if (quotes.isPending) return <div className="skeleton" role="status"><span className="sr-only">견적을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div>
  if (quotes.error) return <div className="notice" role="alert"><p {...requestIdProps(quotes.error)}>견적을 불러오지 못했습니다. {errorMessage(quotes.error)}</p><button type="button" className="btn" onClick={() => void quotes.refetch()}>다시 불러오기</button></div>
  if (!items.length) return null
  // [왜] 검토를 열려면 대상 부품(target_ref)이 필요하다. 견적 목록에는 없어 눌렀을 때 검토 기록에서 읽는다
  async function open(threadId: string) {
    const thread = await getThread(threadId).catch(() => null)
    onOpen(threadId, thread?.target_ref ?? undefined)
  }
  return <section className="part-group" aria-labelledby="quotes-heading">
    <div className="section-head"><h2 id="quotes-heading">견적<span className="group-count">{items.length}</span></h2><span>가격은 저장하지 않고 조회할 때만 봅니다.</span></div>
    <ul className="fact-list">{items.map(item => <li key={item.id}>
      <span><strong>{item.part_number}</strong>× {item.quantity}</span>
      <span className="row-actions">{item.created_at && <time dateTime={item.created_at}>{item.created_at.slice(0, 10)}</time>}
        {item.thread_id && <button type="button" className="btn" aria-label={`${item.part_number} 견적이 나온 검토 열기`} onClick={() => void open(item.thread_id!)}>검토 열기</button>}</span>
      <PriceLookup parts={[item.part_number]} quantity={item.quantity} />
    </li>)}</ul>
  </section>
}
