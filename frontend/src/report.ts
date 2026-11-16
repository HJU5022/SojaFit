/** 인쇄용 대체 검토 보고서의 ECO 칸 값을 저장한 사례 값만으로 만드는 순수 함수(#56). 없는 값은 null(손으로 적는 빈칸)이고 지어 넣지 않는다. */
import type { ApprovedCaseDetail } from './types.ts';

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
