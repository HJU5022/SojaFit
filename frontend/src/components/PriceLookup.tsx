import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { errorMessage, requestIdProps } from '../api/client'
import { fetchPrices } from '../api/prices'

// 판매처 조회는 외부 호출이라 사용자가 누를 때만 한다.
export default function PriceLookup({ parts, quantity }: { parts: string[]; quantity?: number }) {
  const [open, setOpen] = useState(false)
  const validQuantity = quantity === undefined || (Number.isInteger(quantity) && quantity >= 1 && quantity <= 100000)
  const prices = useQuery({ queryKey: ['prices', parts.join(','), quantity], queryFn: ({ signal }) => fetchPrices(parts, signal, quantity), enabled: false, retry: false, gcTime: 0 })
  function toggle() {
    if (!validQuantity) return
    if (!open || (!prices.data && !prices.error && !prices.isFetching)) { void prices.refetch({ cancelRefetch: false }); setOpen(true) }
    else setOpen(false)
  }
  return <div className="approval" data-refresh-blocked={prices.isFetching}>
    <button className="btn" disabled={!validQuantity} aria-expanded={open} onClick={toggle}>{open && (prices.data || prices.error || prices.isFetching) ? '가격·재고 닫기' : '가격·재고 조회'}</button>
    {!validQuantity && <p className="property-note">수량을 1~100000 사이의 정수로 입력해 주세요.</p>}
    {open && (prices.isFetching ? <div className="skeleton" role="status"><span className="sr-only">가격과 재고를 조회하는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div>
      : prices.error ? <div className="notice" role="alert"><p {...requestIdProps(prices.error)}>가격을 조회하지 못했습니다. {errorMessage(prices.error)}</p><button className="btn" onClick={() => void prices.refetch({ cancelRefetch: false })}>다시 조회</button></div>
        : !prices.data ? <p className="property-note">현재 수량으로 가격·재고를 다시 조회해 주세요.</p>
        : !prices.data.available ? <p className="property-note">{prices.data.message}</p>
          : <>
            {prices.data.parts.length === 0 && <p className="property-note">조회된 판매처 부품이 없습니다.</p>}
            {prices.data.parts.map((part, index) => <dl className="price" key={index}>
              <div><dt>품번</dt><dd>{part.part_number || '정보 없음'}</dd></div>
              <div><dt>제조사</dt><dd>{part.manufacturer || '정보 없음'}</dd></div>
              <div><dt>재고</dt><dd>{part.availability || '정보 없음'}</dd></div>
              {part.price_breaks.map((price, row) => <div key={row}><dt>{price.quantity != null ? `${price.quantity}개부터` : '단가'}</dt><dd>{price.price && price.currency ? `${price.price} ${price.currency}` : '정보 없음'}</dd></div>)}
              {quantity !== undefined && (part.estimate ? <><div><dt>적용 구간</dt><dd>{part.estimate.break_quantity}개부터</dd></div><div><dt>적용 단가</dt><dd>{part.estimate.unit_price} {part.estimate.currency}</dd></div><div><dt>예상 금액 ({part.estimate.quantity}개)</dt><dd>{part.estimate.total} {part.estimate.currency}</dd></div></> : <div><dt>예상 금액</dt><dd>품번·가격 구간·통화를 확인하지 못해 계산을 보류했습니다.</dd></div>)}
              {part.product_url && /^https?:\/\//.test(part.product_url) && <div><dt>판매처</dt><dd><a href={part.product_url} target="_blank" rel="noreferrer">열기<ExternalLink aria-hidden="true" /><span className="sr-only"> (새 탭)</span></a></dd></div>}
            </dl>)}
            <p className="property-note">출처 {prices.data.source}, 조회 시각 <time>{prices.data.fetched_at}</time>. 세금, 배송비, 환율은 포함하지 않은 조회 시점의 값입니다.</p>
          </>)}
  </div>
}
