/** 인쇄용 대체 검토 보고서의 ECO 칸 값과 견적서 문서의 값을 저장한 사례 값만으로 만드는 순수 함수(#56). 없는 값은 null(손으로 적는 빈칸)이고 지어 넣지 않는다. */
import type { ApprovedCaseDetail, Prices, Quote } from './types.ts';

/**
 * - role: 회로 역할 표기("RECT 정류"), 모르면 null. verdict: 판정 이름(`verdicts[d.verdict]`).
 * - change: 변경 내용 한 문장. 바꿀 부품·원래 품번·후보 중 하나라도 없으면 반쪽 문장 대신 null.
 * - impact: 변경 영향 한 줄(판정과 통과 조건 수, 기술 검토 근거 절 번호).
 * - row: 영향받는 품목 한 줄(기호 · 설명 · 이전 품번 · 새 품번 · 회로 판 · 적용 날짜 · 재고 상태 · 재고 처리).
 */
export function ecoFields(d: ApprovedCaseDetail, role: string | null, verdict: string) {
  const checks = d.candidate?.checks ?? [],
    passed = checks.filter((check) => check.result.toLowerCase() === 'pass').length;
  return {
    // [왜] 영문 품번 뒤 조사(을/를, 로/으로)는 끝 글자 읽기에 따라 달라 화살표로 쓴다
    change:
      d.target_ref && d.target_value && d.candidate_part
        ? `${d.target_ref} 부품 교체: ${d.target_value} → ${d.candidate_part}`
        : null,
    impact: checks.length
      ? `판정 ${verdict} · 조건 ${checks.length}개 중 ${passed}개 통과(기술 검토 근거 3절)`
      : `판정 ${verdict}(기술 검토 근거 2절)`,
    row: [
      d.target_ref,
      role,
      d.target_value,
      d.candidate_part,
      // [왜] 새 회로 판은 손으로 적는다. 회로 판 0(회로 없음)·null은 이전 판도 빈칸
      d.circuit_version ? `v${d.circuit_version} →` : '→',
      null,
      null,
      null,
    ],
  };
}

/**
 * 견적서 문서의 값(SPEC 8.4 "견적서 문서"). 가격은 문서를 열 때 조회한 응답만 쓰고 저장하지 않는다(ADR 0009).
 * - estimate가 null이면 단가 · 금액은 "조회 불가"이고, 조회는 됐는데 못 쓴 이유가 unavailable에 있다.
 * - prices가 null이면 아직 조회 전이거나 요청이 실패한 것이라 unavailable도 null이다(화면이 따로 알린다).
 */
export function quoteFields(d: ApprovedCaseDetail, quote: Quote, prices: Prices | null) {
  // [왜] Mouser는 비슷한 품번을 여럿 돌려줄 수 있다. 서버가 이 수량의 금액을 계산해 준(estimate) 부품만 쓴다
  const part = prices?.available ? (prices.parts.find((p) => p.estimate) ?? null) : null;
  let unavailable: string | null = null;
  if (prices && !prices.available) unavailable = prices.message;
  else if (prices && !part) unavailable = '이 품번과 수량에 맞는 가격을 확인하지 못했습니다.';
  return {
    number: `SF-Q-${d.id}-${quote.id}`,
    file: `견적서-SF-Q-${d.id}-${quote.id}.pdf`,
    ref: d.target_ref,
    original: d.target_value,
    part: quote.part_number,
    quantity: quote.quantity,
    manufacturer: part?.manufacturer ?? null,
    availability: part?.availability ?? null,
    url: part?.product_url ?? null,
    estimate: part?.estimate ?? null,
    source: prices?.available ? prices.source : null,
    fetchedAt: prices?.available ? prices.fetched_at : null,
    unavailable,
  };
}
