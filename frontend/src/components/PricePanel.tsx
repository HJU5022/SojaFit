import { useEffect, useState } from 'react'
import { errorMessage } from '../api/client'
import { fetchPrices } from '../api/prices'
import type { Prices } from '../api/prices'

export default function PricePanel({ parts }: { parts: string[] }) {
  // 품번 변경은 이전 응답·진행 중 요청·열림 상태를 함께 폐기한다.
  return <Panel key={JSON.stringify(parts)} parts={parts} />
}
function Panel({ parts }: { parts: string[] }) {
  const [open, setOpen] = useState(false)
  return <section className="panel" aria-label="가격·재고">
    <h2>가격·재고</h2><p>판매처 정보는 조회한 화면에서만 표시합니다.</p>
    <button disabled={parts.length === 0} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? '가격·재고 닫기' : '가격·재고 조회'}</button>
    {parts.length === 0 && <p>조회할 후보 품번이 없습니다.</p>}
    {open && <PriceResult parts={parts} />}
  </section>
}
function PriceResult({ parts }: { parts: string[] }) {
  const [result, setResult] = useState<Prices | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [attempt, setAttempt] = useState(0)
  const names = parts.join(',')
  useEffect(() => {
    let current = true
    const controller = new AbortController()
    setError(null)
    fetchPrices(names.split(','), controller.signal).then((result) => { if (current) setResult(result) })
      .catch((error) => { if (current) setError(error) })
    return () => { current = false; controller.abort() }
  }, [names, attempt])
  if (error) return <div><p role="alert">{errorMessage(error)}</p><button className="secondary" onClick={() => setAttempt(value => value + 1)}>가격·재고 다시 조회</button></div>
  if (!result) return <p role="status">가격·재고 조회 중입니다.</p>
  if (!result.available) return <p>{result.message}</p>
  return <div><p>출처: {result.source} · 조회 시각: <time>{result.fetched_at}</time></p>
    {result.parts.length === 0 && <p>조회된 판매처 부품이 없습니다.</p>}
    {result.parts.map((part, index) => <article className="price-part" key={index}>
      <h3>{part.part_number || '품번 정보 없음'}</h3><p>{part.manufacturer || '제조사 정보 없음'}</p><p>{part.availability || '재고 정보 없음'}</p>
      <ul>{part.price_breaks.map((price, index) => <li key={index}>{price.quantity != null && `${price.quantity}개부터: `}<span>{price.price && price.currency ? `${price.price} ${price.currency}` : '가격 정보 없음'}</span></li>)}</ul>
      {part.product_url && <a href={part.product_url} target="_blank" rel="noreferrer">판매처에서 확인</a>}
    </article>)}
  </div>
}
