/** 인쇄용 대체 검토 보고서의 ECO 칸 값 시험(#56): 저장한 값만 채우고 없는 값은 빈칸(null). 네트워크·DOM 없음. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { ecoFields } from '../src/report.ts';
import type { ApprovedCaseDetail } from '../src/types.ts';

const detail: ApprovedCaseDetail = {
  id: 7,
  candidate_part: '1N4007G',
  verdict: 'ROLE_SUFFICIENT',
  created_at: '2026-11-16T12:00:00Z',
  project_id: 1,
  project_name: '전원 보드',
  thread_id: 't1',
  thread_title: '정류 다이오드 대체',
  question: 'D1을 바꿀 수 있나요?',
  target_ref: 'D1',
  target_value: '1N4007RLG',
  circuit_version: 3,
  answer: '',
  candidate: {
    part: '1N4007G',
    role: 'RECT',
    verdict: 'ROLE_SUFFICIENT',
    checks: [
      { code: 'VRRM', result: 'pass' },
      { code: 'IF', result: 'PASS' },
      { code: 'VF', result: 'unknown' },
    ],
    missing: [],
    uncertain: [],
    cautions: [],
    board_change: null,
  },
  evidence: [],
  quotes: [],
};

test('저장 값으로 변경 내용 한 문장, 변경 영향 한 줄, 영향받는 품목 한 줄을 채우고 나머지는 빈칸', () => {
  const eco = ecoFields(detail, 'RECT 정류', '역할상 충분');
  assert.equal(eco.change, 'D1 부품 교체: 1N4007RLG → 1N4007G');
  assert.equal(eco.impact, '판정 역할상 충분 · 조건 3개 중 2개 통과(기술 검토 근거 3절)');
  // 기호 · 설명 · 이전 품번 · 새 품번 · 회로 판 · 적용 날짜 · 재고 상태 · 재고 처리
  assert.deepEqual(eco.row, ['D1', 'RECT 정류', '1N4007RLG', '1N4007G', 'v3 →', null, null, null]);
});

test('바꿀 부품·원래 품번·후보 중 하나라도 없으면 변경 내용은 반쪽 문장 대신 빈칸', () => {
  assert.equal(ecoFields({ ...detail, target_value: null }, null, '역할상 충분').change, null);
  assert.equal(ecoFields({ ...detail, target_ref: null }, null, '역할상 충분').change, null);
  const eco = ecoFields({ ...detail, target_value: null }, null, '역할상 충분');
  assert.equal(eco.row[1], null); // 역할을 모르면 설명도 빈칸
  assert.equal(eco.row[2], null);
});

test('조건별 판정이 없으면 개수 없이 판정만, 회로 판 0·null은 이전 판도 빈칸', () => {
  for (const circuit_version of [0, null]) {
    const eco = ecoFields({ ...detail, candidate: null, circuit_version }, null, '동일품');
    assert.equal(eco.impact, '판정 동일품(기술 검토 근거 2절)');
    assert.equal(eco.row[4], '→');
  }
});
