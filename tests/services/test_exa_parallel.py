"""웹 근거 받기 병렬화 · 판본 불일치 건너뛰기 · 미리 받기 대기 계약. 네트워크 없음(_body · verified_rows를 가짜로 바꿈)."""
import json
import threading
import time

import httpx
import pytest

from backend.services import exa

BASE = 'https://services.taiwansemi.com/storage/resources/datasheet/'
A, B, C = BASE + 'SS34_F16.pdf', BASE + 'SS34_G17.pdf', BASE + 'SS34_H18.pdf'


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'unit-test')
    state = {'urls': [A, B, C], 'gets': [], 'fail': set(), 'delay': 0.0, 'active': 0, 'peak': 0}
    lock = threading.Lock()

    def body(client, method, url, limit, **kwargs):
        if method == 'POST':
            return json.dumps({'results': [{'url': u, 'title': 'SS34 datasheet'} for u in state['urls']]}).encode(), url
        with lock:
            state['gets'].append(url)
            state['active'] += 1
            state['peak'] = max(state['peak'], state['active'])
        try:
            time.sleep(state['delay'])
            if url in state['fail']:
                raise ValueError('broken')
            return b'%PDF-1.7 ' + url.encode(), url
        finally:
            with lock:
                state['active'] -= 1

    monkeypatch.setattr(exa, '_body', body)
    monkeypatch.setattr(exa, 'verified_rows', lambda raw, url, parts, words, grade=None: [
        {'content': f'{url[-8:]} row{i}', 'page': i, 'doc_parts': ['SS34']} for i in (1, 2)])
    return state


def strip(docs):
    return [{k: v for k, v in d.items() if k != 'retrieved_at'} for d in docs]


def run(terms='reverse voltage'):
    return strip(exa.search_evidence(['SS34'], terms, grade=2))


def test_two_downloads_are_assembled_in_candidate_order(env):
    docs = run()
    assert [d['chunk_id'] for d in docs] == ['W1', 'W2', 'W3', 'W4']
    assert [d['source_url'] for d in docs] == [A, A, B, B]
    assert [d['file'] for d in docs] == ['SS34_F16.pdf'] * 2 + ['SS34_G17.pdf'] * 2
    assert sorted(env['gets']) == [A, B]  # 세 번째 후보는 받지 않는다(MAX_DOWNLOADS)


def test_two_downloads_overlap(env):
    env['delay'] = 0.3
    start = time.monotonic()
    run()
    assert env['peak'] == 2 and time.monotonic() - start < 0.55


def test_failed_download_still_uses_its_slot(env):
    env['fail'] = {A}
    docs = run()
    assert [d['source_url'] for d in docs] == [B, B] and [d['chunk_id'] for d in docs] == ['W1', 'W2']
    assert C not in env['gets']


def test_revision_mismatch_is_skipped_but_consumes_its_slot(env):
    docs = run('reverse voltage G17')
    assert env['gets'] == [B]  # A(F16)는 받지 않는다, 슬롯은 썼으므로 C도 받지 않는다
    assert [d['source_url'] for d in docs] == [B, B] and [d['chunk_id'] for d in docs] == ['W1', 'W2']


def test_no_requested_revision_never_skips(env):
    run()
    assert sorted(env['gets']) == [A, B]


def test_skip_only_for_letter_digit_filename(env):
    env['urls'] = [BASE + 'SS34.pdf', BASE + 'SS34_Rev_B.pdf', C]
    run('reverse voltage G17')
    assert sorted(env['gets']) == sorted(env['urls'][:2])


def test_one_from_prefetch_one_direct(env, monkeypatch):
    monkeypatch.setenv('WEB_PREFETCH', '1')
    with exa.request_scope():
        exa.prefetch(['SS34'])
        exa._prefetched.get()['job'].result(timeout=5)
        env['gets'].clear()
        docs = strip(exa.search_evidence(['SS34'], 'reverse voltage', grade=2))
    assert env['gets'] == []  # 미리 받은 A, B를 다시 받지 않는다
    assert [d['source_url'] for d in docs] == [A, A, B, B]


def test_prefetch_miss_url_returns_none_immediately(env, monkeypatch):
    monkeypatch.setenv('WEB_PREFETCH', '1')
    env['urls'] = [A, B, C]
    with exa.request_scope():
        exa.prefetch(['SS34'])
        exa._prefetched.get()['job'].result(timeout=5)
        start = time.monotonic()
        assert exa._from_prefetch(C) is None
        assert exa._from_prefetch(A)[1] == A
        assert time.monotonic() - start < 0.5


def test_prefetch_wait_is_one_budget_per_request(env, monkeypatch):
    monkeypatch.setenv('WEB_PREFETCH', '1')
    monkeypatch.setattr(exa, 'PREFETCH_WAIT_SECONDS', 0.3)
    env['delay'] = 2
    with exa.request_scope():
        exa.prefetch(['SS34'])
        start = time.monotonic()
        assert exa._from_prefetch(A) is None
        assert exa._from_prefetch(B) is None  # 같은 예산을 이미 썼으므로 더 기다리지 않는다
        assert time.monotonic() - start < 0.6
