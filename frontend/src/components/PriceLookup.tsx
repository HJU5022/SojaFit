import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { errorMessage, requestIdProps } from '../api/client'
import { fetchPrices } from '../api/prices'
import { breakFor } from '../lib/price'

// 판매처 조회는 외부 호출이라 사용자가 누를 때만 한다. quantity가 있으면(견적) 그 수량에 맞는 단가와 합계도 보인다.
// [왜] gcTime: 0으로 조회 결과를 캐시에 남기지 않는다. 가격·재고는 저장하지 않는다(Mouser 약관, ADR 0009). 이 값은 요청 본문 · 저장소에 넣지 않는다.
export default function PriceLookup({ parts, quantity }: { parts: string[]; quantity?: number }) {
  const [open, setOpen] = useState(false)
  const prices = useQuery({ queryKey: ['prices', parts.join(',')], queryFn: ({ signal }) => fetchPrices(parts, signal), enabled: false, retry: false, gcTime: 0 })
  function toggle() {
    if (!open) void prices.refetch({ cancelRefetch: false })
    setOpen(value => !value)
  }
  return <div className="approval">
    <button className="btn" aria-expanded={open} onClick={toggle}>{open ? '가격·재고 닫기' : '가격·재고 조회'}</button>
    {open && (prices.isPending ? <div className="skeleton" role="status"><span className="sr-only">가격과 재고를 조회하는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div>
      : prices.error ? <div className="notice" role="alert"><p {...requestIdProps(prices.error)}>가격을 조회하지 못했습니다. {errorMessage(prices.error)}</p><button className="btn" onClick={() => void prices.refetch({ cancelRefetch: false })}>다시 조회</button></div>
        : !prices.data.available ? <p className="property-note">{prices.data.message}</p>
          : <>
            {prices.data.parts.length === 0 && <p className="property-note">조회된 판매처 부품이 없습니다.</p>}
            {prices.data.parts.map((part, index) => {
              const hit = quantity ? breakFor(part.price_breaks, quantity) : null
              return <dl className="price" key={index}>
                <div><dt>품번</dt><dd>{part.part_number || '정보 없음'}</dd></div>
                <div><dt>제조사</dt><dd>{part.manufacturer || '정보 없음'}</dd></div>
                <div><dt>재고</dt><dd>{part.availability || '정보 없음'}</dd></div>
                {quantity ? (hit
                  ? <><div><dt>{quantity}개 단가</dt><dd>{hit.price} {hit.currency}</dd></div><div><dt>{quantity}개 합계</dt><dd>{(hit.unit * quantity).toFixed(2)} {hit.currency}</dd></div></>
                  : <div><dt>{quantity}개 단가</dt><dd>수량에 맞는 가격 구간 없음</dd></div>) : null}
                {part.price_breaks.map((price, row) => <div key={row}><dt>{price.quantity != null ? `${price.quantity}개부터` : '단가'}</dt><dd>{price.price && price.currency ? `${price.price} ${price.currency}` : '정보 없음'}</dd></div>)}
                {part.product_url && /^https?:\/\//.test(part.product_url) && <div><dt>판매처</dt><dd><a href={part.product_url} target="_blank" rel="noreferrer">열기<ExternalLink aria-hidden="true" /><span className="sr-only"> (새 탭)</span></a></dd></div>}
              </dl>
            })}
            <p className="property-note">{prices.data.source} 실시간 조회 · 조회 시각 <time>{prices.data.fetched_at}</time> · 세금·배송비·환율 미포함 · 저장하지 않음</p>
          </>)}
  </div>
}
