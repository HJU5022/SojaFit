/** 인쇄용 대체 검토 보고서의 ECO 칸 시험(#56): 저장한 값만 채우고 나머지는 손으로 적는 빈칸. 보고서 본문을 HTML 문자열로 그려 본다. 네트워크·브라우저 없음. */
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { registerHooks } from 'node:module';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { transformSync } from 'rolldown/utils';
import type { ApprovedCaseDetail } from '../src/types.ts';

// [왜] node --test는 .tsx(JSX)와 확장자 없는 상대 import('./api')를 못 읽어, 빌드가 쓰는 rolldown으로 그 자리에서 바꾼다
registerHooks({
  resolve(spec, ctx, next) {
    if (spec.startsWith('.') && !/\.\w+$/.test(spec))
      for (const ext of ['.ts', '.tsx']) {
        const url = new URL(spec + ext, ctx.parentURL).href;
        if (existsSync(fileURLToPath(url))) return next(url, ctx);
      }
    return next(spec, ctx);
  },
  load(url, ctx, next) {
    if (!url.endsWith('.tsx')) return next(url, ctx);
    const path = fileURLToPath(url),
      { code } = transformSync(path, readFileSync(path, 'utf8'), { jsx: { runtime: 'automatic' } });
    return { format: 'module', source: code, shortCircuit: true };
  },
});
const { ReportBody } = await import('../src/Approved.tsx');

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
      { code: 'VRRM', result: 'pass', threshold: 1000, value: 1000, unit: 'V' },
      { code: 'IF', result: 'PASS', threshold: 1, value: 1, unit: 'A' },
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
const render = (d: ApprovedCaseDetail) =>
  renderToStaticMarkup(
    createElement(ReportBody, { d, roles: [{ code: 'RECT', name: '정류' }], email: 'a@x.dev' }),
  );
const blanks = (html: string) => html.match(/class="report-blank"/g)?.length ?? 0;

test('저장 값으로 변경 내용 한 문장과 영향받는 품목 한 줄을 채우고, 없는 값은 빈칸으로 둔다', () => {
  const html = render(detail);
  assert.ok(html.includes('D1 부품 교체: 1N4007RLG → 1N4007G'));
  assert.ok(html.includes('판정 역할상 충분 · 조건 3개 중 2개 통과(기술 검토 근거 3절)'));
  const row = html.match(/<table class="report-items">.*?<tbody><tr>(.*?)<\/tr>/)?.[1] ?? '';
  const cells = [...row.matchAll(/<td>(.*?)<\/td>/g)].map((m) => m[1].replace(/<[^>]+>/g, ''));
  assert.deepEqual(cells, [
    'D1',
    'RECT 정류',
    '1N4007RLG',
    '1N4007G',
    'v3 →',
    '', // 적용 날짜
    '', // 재고 상태
    '', // 재고 처리
    ' BOM 사양 파일 원가 구매',
  ]);
  // ECR 번호 · 우선순위 · 요청자 · 변경 사유 · 변경 영향 아래 적을 칸
  assert.equal(blanks(html), 5);
  const boxes = html.match(/<input[^>]*>/g) ?? [];
  assert.equal(boxes.length, 5);
  assert.ok(boxes.every((b) => b.includes('type="checkbox"') && !b.includes('checked')));
  // 문서 번호와 ECO 번호, 작성일과 제출일은 하나로 합쳤다
  assert.equal(html.split('SF-7').length - 1, 1);
  assert.ok(!html.includes('문서 번호') && !html.includes('작성일'));
});

test('바꿀 부품·원래 품번·후보 중 하나라도 없으면 변경 내용은 반쪽 문장 대신 빈칸, 회로 판 0은 이전 판도 빈칸', () => {
  const html = render({ ...detail, target_value: null, circuit_version: 0, candidate: null });
  assert.ok(!html.includes('부품 교체'));
  assert.equal(blanks(html), 6);
  assert.ok(html.includes('판정 역할상 충분(기술 검토 근거 2절)'));
  assert.ok(html.includes('<td>→</td>'));
});
