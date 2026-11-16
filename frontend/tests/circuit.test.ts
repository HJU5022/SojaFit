/** 공개 프로젝트의 components·nets를 빠짐없이 표시하는지 검사한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  acceptsFile,
  duplicateAction,
  filterParts,
  isSchematicFile,
  partsOf,
  pinsOf,
  projectNameFromQuestion,
  reviewQuestion,
  unsupportedPartNote,
  unsupportedPartReason,
} from '../src/circuit.ts';
test('공개 components 배열에서 D1과 핀 이름을 보존한다', () => {
  const p: any = {
    connections: {
      components: [{ ref: 'D1', value: '1N4007RLG' }],
      nets: [{ name: 'VIN', nodes: [{ ref: 'D1', pin: '1', pinfunction: 'K' }] }],
    },
  };
  assert.equal(partsOf(p)[0].ref, 'D1');
  assert.deepEqual(pinsOf(p, 'D1'), [{ pin: '1', net: 'VIN', name: 'K' }]);
});
test('업로드 API의 parts 배열도 같은 공개 부품으로 표시한다', () => {
  const p: any = { connections: { parts: [{ ref: 'D2', value: '1N4001' }], nets: [] } };
  assert.equal(partsOf(p)[0]?.ref, 'D2');
});
test('LED·표시기·다이오드가 아닌 부품은 판정 대상에서 이유와 함께 빠진다', () => {
  const led = ' LED라서 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.';
  // 값·풋프린트·설명 어디서든 LED로 읽는다(서버 _require_supported_target과 같은 규칙)
  assert.equal(
    unsupportedPartReason({ ref: 'D2', value: 'LED', footprint: 'LED_THT:LED_D5.0mm' }),
    'D2는' + led,
  );
  assert.equal(
    unsupportedPartReason({ ref: 'D3', value: 'STAT', footprint: 'LED_SMD:LED_0805_2012Metric' }),
    'D3은' + led,
  );
  assert.equal(
    unsupportedPartReason({ ref: 'D3', value: 'RED', description: 'Red LEDs' }),
    'D3은' + led,
  );
  assert.equal(unsupportedPartReason({ ref: 'D3', value: 'LED0805' }), 'D3은' + led);
  assert.equal(
    unsupportedPartReason({ ref: 'D4', value: 'X', description: 'Light emitting diode' }),
    'D4는' + led,
  );
  assert.equal(unsupportedPartReason({ ref: 'LED1', value: 'X' }), 'LED1은' + led);
  assert.equal(
    unsupportedPartReason({ ref: 'D5', value: '7-Segment', footprint: '' }),
    'D5는 표시기라서 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.',
  );
  assert.equal(
    unsupportedPartReason({ ref: 'R1', value: '10k' }),
    'R1은 다이오드가 아니라서 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.',
  );
  // 은/는은 끝 글자를 한국어로 읽은 받침으로 고른다(서버 _topic과 같은 표)
  assert.match(unsupportedPartReason({ ref: 'D10', value: 'LED' }), /^D10은 /);
  assert.match(unsupportedPartReason({ ref: 'D1', value: 'LED' }), /^D1은 /);
  assert.match(unsupportedPartReason({ ref: 'Q1A', value: 'X' }), /^Q1A는 /);
  assert.match(unsupportedPartReason({ ref: 'CN', value: 'X' }), /^CN은 /);
});
test('회로 패널 한 줄은 사실만 말하고 고르라고 하지 않는다(#50)', () => {
  assert.equal(
    unsupportedPartNote({ ref: 'D2', value: 'LED', footprint: 'LED_THT:LED_D5.0mm' }),
    '이 회로의 D2(LED)는 아직 교체 검토를 지원하지 않아요.',
  );
  assert.equal(
    unsupportedPartNote({ ref: 'D5', value: '7-Segment' }),
    '이 회로의 D5(표시기)는 아직 교체 검토를 지원하지 않아요.',
  );
  assert.equal(
    unsupportedPartNote({ ref: 'R1', value: '10k' }),
    '이 회로의 R1(다이오드가 아닌 부품)은 아직 교체 검토를 지원하지 않아요.',
  );
  assert.equal(unsupportedPartNote({ ref: 'D1', value: '1N4007RLG' }), '');
});
test('정류 다이오드는 LED 용도 설명이 있어도 대상으로 남는다', () => {
  assert.equal(
    unsupportedPartReason({
      ref: 'D1',
      value: '1N4007RLG',
      footprint: 'Diode_THT:D_A-405_P7.62mm_Horizontal',
      description: 'Diode',
    }),
    '',
  );
  assert.equal(
    unsupportedPartReason({
      ref: 'D1',
      value: 'SS34',
      footprint: 'Diode_SMD:D_SMA',
      description: 'Schottky diode for LED backlight',
    }),
    '',
  );
  assert.equal(unsupportedPartReason({ ref: 'D1', value: 'Failed', footprint: '' }), ''); // led는 낱말 단위로만 본다
});
test('회로 없이 보낸 질문의 프로젝트 이름은 겹친 공백을 줄인 앞 30자다', () => {
  assert.equal(projectNameFromQuestion('  1N4148\n역전압   몇 V야? '), '1N4148 역전압 몇 V야?');
  assert.equal(projectNameFromQuestion('가'.repeat(40)), '가'.repeat(30));
  assert.equal(projectNameFromQuestion('   '), '새 대화');
});
test('업로드 409 중복: 같은 넷리스트면 그 프로젝트로 잇고, 이름만 겹치면 새로 만든다(#48)', () => {
  const nameOnly = { id: 9, name: 'attiny85-time-switch', matches: ['name'] };
  assert.deepEqual(duplicateAction([nameOnly]), { action: 'create' });
  // 서버가 최근 순으로 주므로 넷리스트가 같은 첫 프로젝트를 고른다
  assert.deepEqual(
    duplicateAction([
      nameOnly,
      { id: 5, name: '샘플', matches: ['netlist'] },
      { id: 3, name: '옛 샘플', matches: ['name', 'netlist'] },
    ]),
    { action: 'continue', projectId: 5, name: '샘플' },
  );
  assert.deepEqual(duplicateAction([]), { action: 'create' });
});
test('첨부 파일 종류: .kicad_sch는 회로도, 받는 확장자 밖은 거절한다(#52)', () => {
  const newChat = '.net,.kicad_sch';
  assert.equal(acceptsFile('board.kicad_sch', newChat), true);
  assert.equal(acceptsFile(' Board.KiCad_Sch ', newChat), true);
  assert.equal(acceptsFile('circuit.net', newChat), true);
  assert.equal(acceptsFile('circuit.txt', newChat), false); // 새 대화는 .txt를 받지 않는다(작업대만)
  assert.equal(acceptsFile('circuit.txt', '.net,.txt,.kicad_sch'), true);
  for (const name of [
    'board.sch',
    'board.kicad_pcb',
    'board.kicad_sch.txt',
    'board.kicad_pro',
    'kicad_sch',
  ])
    assert.equal(acceptsFile(name, newChat), false, name);
  assert.equal(isSchematicFile('board.KICAD_SCH'), true);
  assert.equal(isSchematicFile('board.net'), false);
  assert.equal(isSchematicFile('board.sch'), false); // KiCad 5 옛 형식은 받지 않는다
});
test('부품 점검표의 "이 부품 검토" 질문은 ref를 읽은 받침으로 을/를을 고른다(#68)', () => {
  assert.equal(reviewQuestion('D1'), 'D1을 다른 부품으로 바꿔도 될까?');
  assert.equal(reviewQuestion('D2'), 'D2를 다른 부품으로 바꿔도 될까?'); // 이: 받침 없음
  assert.equal(reviewQuestion('D10'), 'D10을 다른 부품으로 바꿔도 될까?'); // 영
  assert.equal(reviewQuestion('D9'), 'D9를 다른 부품으로 바꿔도 될까?');
});
test('부품 점검표는 종류(빈 값이면 전체)와 판정 지원 부품만으로 거른다(#68)', () => {
  const parts = [
    { ref: 'D1', kind: 'diode', judge_supported: true },
    { ref: 'D2', kind: 'led', judge_supported: false },
    { ref: 'R1', kind: 'resistor', judge_supported: false },
  ];
  const refs = (kind: string, only: boolean) => filterParts(parts, kind, only).map((p) => p.ref);
  assert.deepEqual(refs('', false), ['D1', 'D2', 'R1']);
  assert.deepEqual(refs('led', false), ['D2']);
  assert.deepEqual(refs('', true), ['D1']);
  assert.deepEqual(refs('led', true), []);
});
