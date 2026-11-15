/** 한 검토 결과(메시지)의 승인 목록에서 후보 하나의 승인 상태를 가르는 순수 함수. 승인·견적 저장과 판정은 서버가 한다. 출처: SPEC 4절. */
import type { Approval, Verdict } from './types.ts';

/**
 * 서버는 사례가 남은 활성 승인만 돌려준다(GET /api/messages/{id}/approvals). 그래서
 * - own: 이 후보를 승인한 기록. 있으면 견적을 저장할 수 있다.
 * - other: 이 검토에서 이미 다른 후보를 승인한 기록. 있으면 새 승인은 409(ALREADY_APPROVED)라 승인 버튼을 숨긴다.
 * 승인 사례를 지우면 목록이 비어 둘 다 없고, 같은 검토에서 다시 승인할 수 있다.
 */
export function approvalState(
  approvals: Approval[] | null | undefined,
  candidate: { part: string; verdict: Verdict },
): { own: Approval | undefined; other: Approval | undefined } {
  const own = approvals?.find(
    (a) => a.candidate_part === candidate.part && a.verdict === candidate.verdict,
  );
  return { own, other: own ? undefined : approvals?.[0] };
}
