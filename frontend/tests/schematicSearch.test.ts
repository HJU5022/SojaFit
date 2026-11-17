/** 원본 회로도 검색을 (프로젝트, 회로 버전)마다 한 번만 보내는 규칙 시험. 네트워크·DOM 없음. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { REUSE_MS, searchOnce } from '../src/schematicSearch.ts';
import * as schematic from '../src/schematicSearch.ts';

test('단일 검색은 소유 프로젝트·회로 버전을 유지하고 서버가 원본과 참고 범위를 구분하게 한다', () => {
  assert.equal(typeof schematic.schematicSearchParams, 'function');
  const params = schematic.schematicSearchParams('  TS19371CX6  ', 13, 1, 'thread-13');
  assert.deepEqual(Object.fromEntries(params), {
    q: 'TS19371CX6',
    project_id: '13',
    circuit_version: '1',
    auto_search: 'true',
    thread_id: 'thread-13',
  });
  const selected = schematic.schematicSearchParams(
    'L7805',
    13,
    2,
    null,
    'https://www.st.com/resource/en/datasheet/l78.pdf',
  );
  assert.equal(selected.get('source_url'), 'https://www.st.com/resource/en/datasheet/l78.pdf');
  assert.equal(selected.has('thread_id'), false);
  assert.equal(selected.has('reference_only'), false);
  assert.equal(selected.has('component_type'), false);
});

test('참고 회로를 원본으로 표시하지 않고 공식 출처와 다른 출처를 구분한다', () => {
  assert.equal(typeof schematic.schematicLabel, 'function');
  assert.equal(
    schematic.schematicLabel({ circuit_version: null, source_type: 'manufacturer_official' }),
    '공식 참고 회로',
  );
  assert.equal(
    schematic.schematicLabel({ circuit_version: null, source_type: 'community' }),
    '참고 회로',
  );
  assert.equal(
    schematic.schematicLabel({ circuit_version: 1, source_type: 'manufacturer_official' }),
    '원본 회로도',
  );
  assert.equal(schematic.schematicLabel(null), '원본 회로도');
});

function counter(result: () => Promise<string>) {
  const run = () => {
    run.calls += 1;
    return result();
  };
  run.calls = 0;
  return run;
}

test('찾은 결과는 14분 동안 다시 보내지 않고 그 뒤에는 새로 찾는다', async () => {
  const run = counter(() => Promise.resolve('도면'));
  assert.equal(await searchOnce('1:1', run, false, 0), '도면');
  assert.equal(await searchOnce('1:1', run, false, REUSE_MS - 1), '도면');
  assert.equal(run.calls, 1);
  await searchOnce('1:1', run, false, REUSE_MS);
  assert.equal(run.calls, 2);
});

test('진행 중인 검색은 다시 그려져도 이어받는다', async () => {
  const run = counter(() => new Promise((ok) => setTimeout(() => ok('도면'), 5)));
  const [a, b] = [searchOnce('2:1', run, false, 0), searchOnce('2:1', run, false, 1)];
  assert.equal(a, b);
  assert.equal(await b, '도면');
  assert.equal(run.calls, 1);
});

test('실패(못 찾음·다른 오류)는 자동으로 다시 보내지 않고 다시 시도(fresh)할 때만 보낸다', async () => {
  const missing = counter(() => Promise.reject({ code: 'SCHEMATIC_NOT_FOUND' }));
  await assert.rejects(searchOnce('3:1', missing, false, 0));
  await assert.rejects(searchOnce('3:1', missing, false, REUSE_MS * 10));
  assert.equal(missing.calls, 1);
  const down = counter(() => Promise.reject({ code: '' }));
  await assert.rejects(searchOnce('4:1', down, false, 0));
  await assert.rejects(searchOnce('4:1', down, false, 1));
  await assert.rejects(searchOnce('4:1', down, false, REUSE_MS * 10));
  assert.equal(down.calls, 1);
  await assert.rejects(searchOnce('4:1', down, true, REUSE_MS * 10));
  assert.equal(down.calls, 2);
});

test('직접 찾기가 실패해도 앞서 찾은 결과는 다음에 열 때 그대로 쓴다', async () => {
  for (const [key, error] of [
    ['6:1', { code: 'SCHEMATIC_NOT_FOUND' }],
    ['7:1', { code: '' }],
  ] as const) {
    const found = counter(() => Promise.resolve('도면'));
    await searchOnce(key, found, false, 0);
    const manual = counter(() => Promise.reject(error));
    await assert.rejects(searchOnce(key, manual, true, 1));
    assert.equal(await searchOnce(key, found, false, 2), '도면');
    assert.equal(found.calls, 1);
  }
});

test('사용자가 직접 찾으면(fresh) 남은 결과가 있어도 새로 찾고 그 결과를 남긴다', async () => {
  let n = 0;
  const run = counter(() => Promise.resolve(`도면${++n}`));
  await searchOnce('5:1', run, false, 0);
  assert.equal(await searchOnce('5:1', run, true, 1), '도면2');
  assert.equal(await searchOnce('5:1', run, false, 2), '도면2');
  assert.equal(run.calls, 2);
});
