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
  sameOriginImage,
  withoutCorpusCitations,
  safeLink,
} from '../src/display.ts';
import { inputPlaceholder } from '../src/inputLabels.ts';

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

test('sameOriginImage는 같은 출처 경로만 허용한다', () => {
  assert.equal(sameOriginImage('/circuit-schematics/a.png'), '/circuit-schematics/a.png');
  assert.equal(
    sameOriginImage('/api/external-circuits/schematics/t/0?reference_only=true'),
    '/api/external-circuits/schematics/t/0?reference_only=true',
  );
  for (const bad of [
    'https://evil.example/a.png',
    '//evil.example/a.png',
    '/\\evil.example',
    'javascript:1',
    '',
    null,
    undefined,
  ]) {
    assert.equal(sameOriginImage(bad), undefined, String(bad));
  }
});

test('withoutCorpusCitations는 등록된 번호만 숨기고 나머지는 둔다', () => {
  const evidence = [{ citation_number: '79' }, { citation_number: '80' }, {}];
  assert.equal(
    withoutCorpusCitations('누설 전류는 낮습니다 [79] [80].', evidence),
    '누설 전류는 낮습니다.',
  );
  assert.equal(withoutCorpusCitations('값 [79, 12]', evidence), '값 [12]');
  assert.equal(
    withoutCorpusCitations('코드 a[79] [미등록] [링크](https://x.example)', evidence),
    '코드 a [미등록] [링크](https://x.example)',
  );
  assert.equal(withoutCorpusCitations('인용 [79]', []), '인용 [79]');
});

test('inputPlaceholder는 코드 종류별 안내를 주고 모르는 코드는 단위를 추정하지 않는다', () => {
  assert.equal(inputPlaceholder('v_drop_allowed'), '예: 0.5 V');
  assert.equal(inputPlaceholder('v_in_max'), '예: 12 V');
  assert.equal(inputPlaceholder('i_fault'), '예: 1 A');
  assert.equal(inputPlaceholder('pwm'), '예 또는 아니오');
  assert.equal(inputPlaceholder('unknown_code'), '아는 값을 입력해 주세요. 모르면 비워 두세요.');
});
