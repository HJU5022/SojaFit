/** 데이터시트 서재 주소의 검색 조건 읽기·쓰기와 검색어가 든 표지 품번 시험(#67). 네트워크·DOM 없음. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { libraryQueryString, matchedParts, readLibraryQuery } from '../src/libraryQuery.ts';

test('깊은 링크의 조건을 읽고, 잘못된 쪽 번호는 1쪽이다', () => {
  assert.deepEqual(readLibraryQuery('?q=%20SS34%20'), { q: 'SS34', category: '', page: 1 });
  assert.deepEqual(readLibraryQuery('q=1N4148&category=switching-diode&page=3'), {
    q: '1N4148',
    category: 'switching-diode',
    page: 3,
  });
  for (const page of ['0', '-2', '1.5', 'abc', ''])
    assert.equal(readLibraryQuery('?page=' + page).page, 1);
});

test('빈 값과 1쪽은 빼고, 읽은 조건을 그대로 다시 만든다', () => {
  assert.equal(libraryQueryString({ q: '', category: '', page: 1 }), '');
  assert.equal(libraryQueryString({ q: 'SS34', category: '', page: 1 }), '?q=SS34');
  const query = { q: 'MBR 20&40', category: 'schottky-rectifier', page: 2 };
  assert.equal(libraryQueryString(query), '?q=MBR+20%2640&category=schottky-rectifier&page=2');
  assert.deepEqual(readLibraryQuery(libraryQueryString(query)), query);
});

test('검색어가 든 표지 품번만 대소문자 무시로 고른다', () => {
  const parts = ['SS32', 'SS33', 'SS34', 'SS34L'];
  assert.deepEqual(matchedParts(parts, ' ss34 '), ['SS34', 'SS34L']);
  assert.deepEqual(matchedParts(parts, 'SERIES'), []);
  assert.deepEqual(matchedParts(parts, ''), []);
});
