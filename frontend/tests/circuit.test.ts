/** 공개 프로젝트의 components·nets를 빠짐없이 표시하는지 검사한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { partsOf, pinsOf } from '../src/circuit.ts';
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
