import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { errorMessage, requestIdProps } from '../api/client'
import { fetchPrices } from '../api/prices'

// 판매처 조회는 외부 호출이라 사용자가 누를 때만 한다.
export default function PriceLookup({ parts }: { parts: string[] }) {
  const [open, setOpen] = useState(false)
  const prices = useQuery({ queryKey: ['prices', parts.join(',')], queryFn: ({ signal }) => fetchPrices(parts, signal), enabled: open, retry: false, gcTime: 0 })
  return <div className="approval">
    <button className="btn" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? '가격·재고 닫기' : '가격·재고 조회'}</button>
    {open && (prices.isPending ? <div className="skeleton" role="status"><span className="sr-only">가격과 재고를 조회하는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div>
      : prices.error ? <div className="notice" role="alert"><p {...requestIdProps(prices.error)}>가격을 조회하지 못했습니다. {errorMessage(prices.error)}</p><button className="btn" onClick={() => void prices.refetch()}>다시 조회</button></div>
        : !prices.data.available ? <p className="property-note">{prices.data.message}</p>
          : <>
            {prices.data.parts.length === 0 && <p className="property-note">조회된 판매처 부품이 없습니다.</p>}
            {prices.data.parts.map((part, index) => <dl className="price" key={index}>
              <div><dt>품번</dt><dd>{part.part_number || '정보 없음'}</dd></div>
              <div><dt>제조사</dt><dd>{part.manufacturer || '정보 없음'}</dd></div>
              <div><dt>재고</dt><dd>{part.availability || '정보 없음'}</dd></div>
              {part.price_breaks.map((price, row) => <div key={row}><dt>{price.quantity != null ? `${price.quantity}개부터` : '단가'}</dt><dd>{price.price && price.currency ? `${price.price} ${price.currency}` : '정보 없음'}</dd></div>)}
              {part.product_url && /^https?:\/\//.test(part.product_url) && <div><dt>판매처</dt><dd><a href={part.product_url} target="_blank" rel="noreferrer">열기<ExternalLink aria-hidden="true" /><span className="sr-only"> (새 탭)</span></a></dd></div>}
            </dl>)}
            <p className="property-note">출처 {prices.data.source}, 조회 시각 <time>{prices.data.fetched_at}</time>. 세금, 배송비, 환율은 포함하지 않은 조회 시점의 값입니다.</p>
          </>)}
  </div>
}
