/** 화면 표기 함수 시험: 긴 소수 반올림, 기준식·회로 값 이름의 한국어 풀이, 인용 번호 숨김, http(s)·같은 출처만 허용, 입력칸 안내, 수량·가격 조회 경로·예상 금액, 보내기 키(#38), 진행 단계 시간(#42), 판정 후보 모으기(#55). 네트워크·DOM 없음. */
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  basisLabel,
  EVIDENCE_GRADES,
  evidenceGrade,
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
  validQuantity,
  pricesPath,
  estimateRows,
  isSendKey,
  addStep,
  stepMs,
  seconds,
  replyCandidates,
  type Step,
} from '../src/display.ts';
import type { Candidate } from '../src/types.ts';
import { INPUT_LABELS, isBooleanInput, inputPlaceholder } from '../src/inputLabels.ts';

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

test('validQuantity는 수량이 없거나 1~100000 정수일 때만 받는다', () => {
  assert.equal(validQuantity(undefined), true);
  assert.equal(validQuantity(1), true);
  assert.equal(validQuantity(100000), true);
  for (const bad of [0, -1, 100001, 2.5, Number.NaN]) assert.equal(validQuantity(bad), false);
});

test('pricesPath는 수량이 있을 때만 quantity를 붙이고 제조사 접두어를 뗀다', () => {
  assert.equal(pricesPath('1N4007G'), '/prices?parts=1N4007G');
  assert.equal(pricesPath('TSC 1N4007G', 250), '/prices?parts=1N4007G&quantity=250');
  assert.equal(pricesPath('A B/C', 1), '/prices?parts=A%20B%2FC&quantity=1');
});

test('estimateRows는 구간·단가·금액 줄을 만들고 estimate가 없으면 보류 안내를 준다', () => {
  const estimate = {
    quantity: 250,
    break_quantity: 100,
    unit_price: '0.12',
    total: '30.00',
    currency: 'USD',
  };
  assert.deepEqual(estimateRows(estimate), [
    ['적용 구간', '100개부터'],
    ['적용 단가', '0.12 USD'],
    ['예상 금액 (250개)', '30.00 USD'],
  ]);
  for (const none of [null, undefined]) {
    const rows = estimateRows(none);
    assert.equal(rows.length, 1);
    assert.match(rows[0][1], /계산을 보류/);
  }
});
test('Enter는 보내고 Shift+Enter와 한글 조합 중 Enter는 보내지 않는다(#38)', () => {
  const key = (over: Partial<Parameters<typeof isSendKey>[0]>) =>
    isSendKey({ key: 'Enter', shiftKey: false, isComposing: false, keyCode: 13, ...over });
  assert.equal(key({}), true);
  assert.equal(key({ shiftKey: true }), false);
  assert.equal(key({ isComposing: true }), false);
  assert.equal(key({ keyCode: 229 }), false); // 조합 확정 Enter를 isComposing 없이 알리는 브라우저
  assert.equal(key({ key: 'a', keyCode: 65 }), false);
});

test('진행 단계 시간: 프레임 도착 시각으로 단계마다 재고, 재계획은 같은 줄에 이어 더한다(#42)', () => {
  let steps: Step[] = [];
  steps = addStep(steps, '입력 확인', 0);
  steps = addStep(steps, '품번 확인', 400);
  steps = addStep(steps, '질문 분석', 1500);
  assert.deepEqual(
    steps.map((s) => s.stage),
    ['입력 확인', '품번 확인', '질문 분석'],
  );
  assert.equal(seconds(stepMs(steps, 0, 2000)), '0.4초');
  assert.equal(seconds(stepMs(steps, 1, 2000)), '1.1초');
  assert.equal(seconds(stepMs(steps, 2, 2000)), '0.5초'); // 지금 단계는 now까지 늘어난다
  assert.equal(seconds(stepMs(steps, 2, 3700)), '2.2초');
  // 재계획: 품번 확인이 다시 오면 끝으로 옮기고 앞서 쓴 1.1초에 이어 센다
  steps = addStep(steps, '품번 확인', 3000);
  assert.deepEqual(
    steps.map((s) => s.stage),
    ['입력 확인', '질문 분석', '품번 확인'],
  );
  assert.equal(seconds(stepMs(steps, 1, 3000)), '1.5초');
  assert.equal(seconds(stepMs(steps, 2, 3500)), '1.6초');
  assert.equal(seconds(-5), '0.0초');
});

test('면책 문구는 판정 후보가 있는 답에만: 판정 없는 답(일상 대화 · 부품 목록)은 후보가 비고, 같은 후보는 한 번만 센다(#55)', () => {
  assert.deepEqual(replyCandidates({}), []);
  assert.deepEqual(replyCandidates({ roles: ['reverse_protection'], capped: false }), []);
  const ss14 = {
    part: 'SS14',
    role: 'reverse_protection',
    verdict: 'SPEC_EQUIVALENT',
  } as Candidate;
  const ss16 = { ...ss14, part: 'SS16', verdict: 'NOT_VERIFIED' } as Candidate;
  assert.deepEqual(
    replyCandidates({ results: [ss14], shown: [ss14], unverified: [ss16] }).map((c) => c.part),
    ['SS14', 'SS16'],
  );
});

test('예/아니오 조건은 op_amp를 포함하고 수치·알 수 없는 코드는 제외한다', () => {
  for (const [code, label] of Object.entries(INPUT_LABELS)) {
    assert.equal(isBooleanInput(code), code === 'op_amp' || label.includes('(예/아니오)'), code);
  }
  for (const code of ['orig_schottky', 'high_impedance', 'fast_signal', 'op_amp']) {
    assert.equal(isBooleanInput(code), true, code);
  }
  for (const code of ['v_in_max', 'VF', 'unknown_code', '__proto__']) {
    assert.equal(isBooleanInput(code), false, code);
  }
});

test('근거 등급: 서버가 준 등급은 그대로, 웹 표시가 없는 근거는 1등급, 등급 없는 웹 근거는 표기하지 않는다', () => {
  // 등록된 데이터시트 근거: 서버가 등급 · 출처 종류를 붙이지 않는다
  assert.deepEqual(evidenceGrade({}), EVIDENCE_GRADES[0]);
  assert.deepEqual(
    evidenceGrade({ evidence_grade: 2, source_type: 'external_web' }),
    EVIDENCE_GRADES[1],
  );
  assert.deepEqual(
    evidenceGrade({ evidence_grade: 3, source_type: 'web_reference' }),
    EVIDENCE_GRADES[2],
  );
  // [주의] 웹 근거인데 등급이 없으면(서버가 검사하지 못한 옛 기록) 1등급으로 올려 적지 않는다
  assert.equal(evidenceGrade({ source_type: 'external_web' }), null);
  // 배지는 짧게, 이름 · 쓰임은 설명 팝업이 쓴다. 3등급은 판정 근거가 아님을 밝힌다(SPEC 2절)
  assert.deepEqual(
    EVIDENCE_GRADES.map((g) => [g.short, g.name]),
    [
      ['1등급', '등록된 데이터시트'],
      ['2등급', '제조사 공식 문서'],
      ['3등급', '미검증 참고 정보'],
    ],
  );
  assert.match(EVIDENCE_GRADES[2].use, /판정 근거로 쓰지 않습니다/);
});
