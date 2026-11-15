/** SSE 경계·UTF-8 분할·종료 누락을 확인한다. 출처: SPEC 4절. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { consumeSSE } from '../src/stream.ts';

test('바이트마다 나뉜 한국어 프레임을 순서대로 받는다', async () => {
  const bytes = new TextEncoder().encode(
    'event: run_started\r\ndata: {"run_id":"demo"}\r\n\r\nevent: status\ndata: {"stage":"입력 확인"}\n\nevent: completed\ndata: {"answer":"같은 동작은 보장하지 않습니다."}\n\n',
  );
  const input = new ReadableStream({
    start(c) {
      for (const byte of bytes) c.enqueue(new Uint8Array([byte]));
      c.close();
    },
  });
  const frames: any[] = [];
  await consumeSSE(input, (event, data) => frames.push([event, data]));
  assert.deepEqual(
    frames.map((x) => x[0]),
    ['run_started', 'status', 'completed'],
  );
  assert.equal(frames[1][1].stage, '입력 확인');
});
test('최종 이벤트 없는 연결 종료는 복원 대상으로 알린다', async () => {
  const input = new ReadableStream({
    start(c) {
      c.enqueue(new TextEncoder().encode('event: status\ndata: {"status":"running"}\n\n'));
      c.close();
    },
  });
  await assert.rejects(() => consumeSSE(input, () => {}), /연결/);
});
