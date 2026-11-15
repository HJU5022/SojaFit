/** 공개 프로젝트의 components·nets를 빠짐없이 표시하는지 검사한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { partsOf, pinsOf, unsupportedPartReason } from '../src/circuit.ts';
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
  const led =
    '은(는) LED로 식별됩니다. 현재 LED 대체 판정은 지원하지 않습니다. 일반 다이오드를 선택해 주세요.';
  // 값·풋프린트·설명 어디서든 LED로 읽는다(서버 _require_supported_target과 같은 규칙)
  assert.equal(
    unsupportedPartReason({ ref: 'D2', value: 'LED', footprint: 'LED_THT:LED_D5.0mm' }),
    'D2' + led,
  );
  assert.equal(
    unsupportedPartReason({ ref: 'D3', value: 'STAT', footprint: 'LED_SMD:LED_0805_2012Metric' }),
    'D3' + led,
  );
  assert.equal(
    unsupportedPartReason({ ref: 'D3', value: 'RED', description: 'Red LEDs' }),
    'D3' + led,
  );
  assert.equal(unsupportedPartReason({ ref: 'D3', value: 'LED0805' }), 'D3' + led);
  assert.equal(
    unsupportedPartReason({ ref: 'D4', value: 'X', description: 'Light emitting diode' }),
    'D4' + led,
  );
  assert.equal(unsupportedPartReason({ ref: 'LED1', value: 'X' }), 'LED1' + led);
  assert.match(
    unsupportedPartReason({ ref: 'D5', value: '7-Segment', footprint: '' }),
    /^D5은\(는\) 표시기로 식별됩니다/,
  );
  assert.equal(
    unsupportedPartReason({ ref: 'R1', value: '10k' }),
    'R1은(는) 현재 판정 범위 밖입니다. 지금은 다이오드만 판정합니다.',
  );
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
