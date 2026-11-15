/** 화면 표기 함수 시험: 긴 소수 반올림, 판정 기준식의 한국어 풀이, http(s) 링크만 허용. 네트워크·DOM 없음. */
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  basisLabel,
  explainAnswer,
  explainNames,
  opLabel,
  formatAmount,
  formatNumber,
  markdownUrl,
  roundLongDecimals,
  safeLink,
} from '../src/display.ts';

test('formatNumber는 긴 소수만 줄이고 정수·짧은 소수는 그대로 둔다', () => {
  assert.equal(formatNumber(0.17142857142857143), '0.171');
  assert.equal(formatNumber(18.75), '18.75');
  assert.equal(formatNumber(1000), '1000');
  assert.equal(formatNumber(0.0625), '0.0625');
  assert.equal(formatNumber(1.4142135623730951), '1.41');
  assert.equal(formatNumber(12345.678), '12346'); // toPrecision(3)이면 '1.23e+4'가 된다
  assert.equal(formatNumber(-0.17142857142857143), '-0.171');
  assert.equal(formatNumber(Number.NaN), 'NaN');
});

test('formatAmount는 값이 없으면 확인 안 됨, 범위는 ~로 잇고 단위를 붙인다', () => {
  assert.equal(formatAmount(0.17142857142857143, 'A'), '0.171 A');
  assert.equal(formatAmount([3.42, 3.78], 'V'), '3.42 ~ 3.78 V');
  assert.equal(formatAmount(null, 'V'), '확인 안 됨');
  assert.equal(formatAmount(1000), '1000');
});

test('roundLongDecimals는 문장 속 긴 소수만 줄인다', () => {
  assert.equal(roundLongDecimals('필요 값 >= 0.17142857142857143 A'), '필요 값 >= 0.171 A');
  assert.equal(roundLongDecimals('1N4007G 18.75 V, 페이지 12.5'), '1N4007G 18.75 V, 페이지 12.5');
});

test('basisLabel은 기준식의 이름을 한국어로 풀고 모르는 이름이 있으면 원문을 돌려준다', () => {
  assert.deepEqual(basisLabel('v_in_max * kV'), {
    text: '입력 전원 최대 전압 × 전압 여유 1.25배',
    known: true,
  });
  assert.deepEqual(basisLabel('i_max * kI'), {
    text: '다이오드 최대 순방향(부하) 전류 × 전류 여유 1.43배',
    known: true,
  });
  assert.equal(basisLabel('orig.IFSM').text, '원래 부품 IFSM');
  assert.equal(
    basisLabel('TRR >= orig.TRR 또는 CJ >= orig.CJ').text,
    'TRR ≥ 원래 부품 TRR 또는 CJ ≥ 원래 부품 CJ',
  );
  assert.equal(basisLabel('(v_in_min - v_dd_min) / n_diodes').known, true);
  assert.equal(basisLabel('v_ac_rms * 1.41421356 * kV').text.includes('1.41 ×'), true);
  assert.equal(
    basisLabel('같은 기본 품번, 주문 코드만 다름').text,
    '같은 기본 품번, 주문 코드만 다름',
  );
  assert.deepEqual(basisLabel('v_unknown * kV'), { text: 'v_unknown * kV', known: false });
  assert.equal(basisLabel('constructor').known, false); // 객체 기본 속성 이름을 이름표로 오해하지 않는다
});

test('safeLink와 markdownUrl은 http(s)만 허용한다', () => {
  assert.equal(safeLink('https://example.com/a.pdf'), 'https://example.com/a.pdf');
  assert.equal(safeLink('HTTP://example.com/'), 'http://example.com/');
  for (const bad of [
    'javascript:alert(1)',
    'data:text/html,x',
    'mailto:a@b.c',
    '/relative',
    '//host/x',
    '',
    null,
    undefined,
  ]) {
    assert.equal(safeLink(bad), undefined, String(bad));
  }
  assert.equal(safeLink(' javascript:alert(1)'), undefined);
  assert.equal(markdownUrl('https://example.com'), 'https://example.com/');
  assert.equal(markdownUrl('javascript:alert(1)'), '');
});

test('explainAnswer는 답변 표의 괄호 기준식만 풀고 다른 괄호는 건드리지 않는다', () => {
  const row = '| VRRM >= | 18.75 (v_in_max * kV) | 1000 V | 통과 |';
  assert.equal(
    explainAnswer(row),
    '| VRRM >= | 18.75 (입력 전원 최대 전압 × 전압 여유 1.25배) | 1000 V | 통과 |',
  );
  const other =
    '역할: R01 (근거: D1.K → Net-(D1-K)) IFSM >= 2 (2.0) (TA = 25°C unless otherwise noted)';
  assert.equal(explainAnswer(other), other);
});

test('opLabel과 explainNames는 서버 연산자와 회로 값 이름을 화면 표기로 바꾼다', () => {
  assert.equal(opLabel('>='), '≥');
  assert.equal(opLabel('<='), '≤');
  assert.equal(opLabel('within'), '범위 안');
  assert.equal(opLabel('='), '=');
  assert.equal(
    explainNames('빠진 값: v_drop_allowed, 온도'),
    '빠진 값: 다이오드에서 허용하는 전압 강하, 온도',
  );
  assert.equal(explainNames('unknown_name 그대로'), 'unknown_name 그대로');
});
