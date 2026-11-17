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


def test_percent_encoded_filename_is_decoded_like_corpus(env):
    env['urls'] = [BASE + 'UF4001%20SERIES_P2104.pdf']
    docs = run()
    assert [(d['file'], d['title']) for d in docs] == [('UF4001 SERIES_P2104.pdf', 'UF4001 SERIES_P2104.pdf')] * 2
    assert docs[0]['source_url'].endswith('UF4001%20SERIES_P2104.pdf')  # 받는 주소는 인코딩된 그대로다


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


def test_aec_q101_token_is_not_a_revision(env):
    run('reverse voltage AEC Q101')
    assert sorted(env['gets']) == [A, B]  # Q101은 개정 코드 꼴이 아니라 건너뛰지 않는다


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


def test_early_download_is_parsed_before_slow_one_ends_and_parses_never_overlap(env, monkeypatch):
    # 두 번째 후보(B)가 먼저 받아지면 A의 받기가 끝나기 전에 B 파싱이 시작된다. 파싱은 겹치지 않고 결과는 원래 순서다
    delays, events, lock = {A: 0.4, B: 0.0}, [], threading.Lock()
    base_body, active = exa._body, {'now': 0, 'peak': 0}

    def body(client, method, url, limit, **kwargs):
        if method == 'GET':
            time.sleep(delays[url])
            with lock:
                events.append(('dl_end', url, time.monotonic()))
            return b'%PDF-1.7 ' + url.encode(), url
        return base_body(client, method, url, limit, **kwargs)

    def rows(raw, url, parts, words, grade=None):
        with lock:
            events.append(('parse_start', url, time.monotonic()))
            active['now'] += 1
            active['peak'] = max(active['peak'], active['now'])
        time.sleep(0.1)
        with lock:
            active['now'] -= 1
        return [{'content': f'{url[-8:]} row{i}', 'page': i, 'doc_parts': ['SS34']} for i in (1, 2)]

    monkeypatch.setattr(exa, '_body', body)
    monkeypatch.setattr(exa, 'verified_rows', rows)
    docs = run()
    t = {(kind, url): at for kind, url, at in events}
    assert t[('parse_start', B)] < t[('dl_end', A)]
    assert t[('parse_start', A)] >= t[('dl_end', A)] and active['peak'] == 1
    assert [d['source_url'] for d in docs] == [A, A, B, B] and [d['chunk_id'] for d in docs] == ['W1', 'W2', 'W3', 'W4']
