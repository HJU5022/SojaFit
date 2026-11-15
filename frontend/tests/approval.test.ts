/** 승인 목록에서 후보의 승인 상태를 가르는 규칙 시험: 사례를 지운 뒤 다시 승인할 수 있다. 네트워크·DOM 없음. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { approvalState } from '../src/approval.ts';

const saved = [{ id: 7, candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT' as const }];

test('같은 후보·판정의 승인이 있으면 own이고 other는 없다', () => {
  const state = approvalState(saved, { part: 'SS34', verdict: 'ROLE_SUFFICIENT' });
  assert.equal(state.own?.id, 7);
  assert.equal(state.other, undefined);
});

test('다른 후보를 승인한 검토에서는 other만 있어 승인 버튼을 숨긴다', () => {
  const state = approvalState(saved, { part: 'SS33', verdict: 'ROLE_SUFFICIENT' });
  assert.equal(state.own, undefined);
  assert.equal(state.other?.candidate_part, 'SS34');
  // 같은 후보라도 판정이 바뀌었으면 그 승인은 이 판정의 것이 아니다
  assert.equal(approvalState(saved, { part: 'SS34', verdict: 'SPEC_EQUIVALENT' }).own, undefined);
});

test('사례를 지워 목록이 비면(서버는 활성 승인만 준다) own도 other도 없어 다시 승인할 수 있다', () => {
  for (const empty of [[], null, undefined]) {
    const state = approvalState(empty, { part: 'SS34', verdict: 'ROLE_SUFFICIENT' });
    assert.deepEqual(state, { own: undefined, other: undefined });
  }
});
