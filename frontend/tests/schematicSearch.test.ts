/** 원본 회로도 검색을 (프로젝트, 회로 버전)마다 한 번만 보내는 규칙 시험. 네트워크·DOM 없음. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { REUSE_MS, searchOnce } from '../src/schematicSearch.ts';

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

test('못 찾음은 시간이 지나도 다시 보내지 않고, 다른 오류는 바로 다시 보낸다', async () => {
  const missing = counter(() => Promise.reject({ code: 'SCHEMATIC_NOT_FOUND' }));
  await assert.rejects(searchOnce('3:1', missing, false, 0));
  await assert.rejects(searchOnce('3:1', missing, false, REUSE_MS * 10));
  assert.equal(missing.calls, 1);
  const down = counter(() => Promise.reject({ code: '' }));
  await assert.rejects(searchOnce('4:1', down, false, 0));
  await assert.rejects(searchOnce('4:1', down, false, 1));
  assert.equal(down.calls, 2);
});

test('사용자가 직접 찾으면(fresh) 남은 결과가 있어도 새로 찾고 그 결과를 남긴다', async () => {
  let n = 0;
  const run = counter(() => Promise.resolve(`도면${++n}`));
  await searchOnce('5:1', run, false, 0);
  assert.equal(await searchOnce('5:1', run, true, 1), '도면2');
  assert.equal(await searchOnce('5:1', run, false, 2), '도면2');
  assert.equal(run.calls, 2);
});
