"""적재 도구(backend/rag/ingest.py): 벡터 캐시 복구, 없는 본문만 임베딩, DB 재실행(rag-pipeline EC-04·05).

DB 재실행 시험은 TEST_DATABASE_URL을 줄 때만 돈다(CI에는 DB가 없다). 임시 스키마를 만들고 끝나면 지운다.
[주의] DATABASE_URL은 .env의 서비스 DB(Supabase)를 가리킬 수 있어 쓰지 않는다. 로컬 compose DB 주소만 TEST_DATABASE_URL로 준다.
"""
import json
import os
import uuid

import numpy as np
import pytest

from backend.rag import ingest
from backend.rag.ingest import DIM, VectorCache
from backend.services import llm


def fake_embed(calls):
    """호출된 본문을 calls에 적고 본문 길이로 만든 벡터를 돌려주는 가짜 임베딩."""
    def embed(texts):
        calls.append(list(texts))
        return [np.full(DIM, len(t), np.float32) for t in texts], 0, 'fake', 'fake'
    return embed


def test_cache_survives_reopen(tmp_path):
    a, b = np.full(DIM, 0.5, np.float32), np.arange(DIM, dtype=np.float32)
    VectorCache(tmp_path).add([('sha-a', a)])
    VectorCache(tmp_path).add([('sha-b', b)])  # 다시 열어 이어 붙인다
    cache = VectorCache(tmp_path)
    assert set(cache.index) == {'sha-a', 'sha-b'}
    assert np.array_equal(cache.get('sha-a'), a) and np.array_equal(cache.get('sha-b'), b)


def test_cache_recovers_after_interrupted_write(tmp_path):
    VectorCache(tmp_path).add([('sha-a', np.ones(DIM, np.float32)), ('sha-b', np.zeros(DIM, np.float32))])
    with open(tmp_path / 'vectors.sha.txt', 'a', encoding='utf-8') as fs:
        fs.write('sha-c\n')  # 벡터 없이 sha만 쓰고 끊긴 경우
    with open(tmp_path / 'vectors.f32', 'ab') as fv:
        np.ones(DIM // 2, np.float32).tofile(fv)  # 벡터를 반쯤 쓰고 끊긴 경우
    cache = VectorCache(tmp_path)
    assert set(cache.index) == {'sha-a', 'sha-b'} and cache.vecs.shape == (2, DIM)
    assert set(VectorCache(tmp_path).index) == {'sha-a', 'sha-b'}  # 파일도 고쳐져 다시 열어도 같다


def test_fill_cache_embeds_only_missing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, 'embed_texts', fake_embed(calls))
    cache = VectorCache(tmp_path)
    cache.add([('sha-a', np.ones(DIM, np.float32))])
    assert ingest.fill_cache(cache, {'sha-a': 'aaa', 'sha-b': 'bb'}) == 1
    assert calls == [['bb']]


@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='TEST_DATABASE_URL을 줄 때만 돈다')
def test_rerun_skips_rows_and_api(tmp_path, monkeypatch):
    import psycopg
    base, schema = os.environ['TEST_DATABASE_URL'], f'test_ingest_{uuid.uuid4().hex[:8]}'
    url = base + ('&' if '?' in base else '?') + f'options=-csearch_path%3D{schema},public'
    file = 'A SERIES_X1234.pdf'
    # 공통 값(제조사·수집일·파서·이용 조건)은 실제 manifest처럼 빼서 DOC_DEFAULTS로 채워지는지 본다
    doc = {'doc_id': ingest.doc_key(file), 'title': 'A SERIES', 'source_url': f'https://a.b/{file}', 'revision': 'X1234',
           'sha256': '1' * 64, 'chars_original': 10, 'chars_kept': 10, 'truncated': False}
    cards = [{'doc': file, 'idx': i, 'text': t, 'sha256': s, 'page': 1, 'table': None, 'row': None}
             for i, (t, s) in enumerate([('cover', 'a' * 64), ('VRRM 40 V', 'b' * 64)])]
    (tmp_path / 'm.jsonl').write_text(json.dumps(doc) + '\n', encoding='utf-8')
    (tmp_path / 'c.jsonl').write_text(''.join(json.dumps(c) + '\n' for c in cards), encoding='utf-8')
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA {schema}')
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(open('db/02_rag_corpus.sql', encoding='utf-8').read())
        calls = []
        monkeypatch.setattr(llm, 'embed_texts', fake_embed(calls))
        monkeypatch.setenv('DATABASE_URL', url)
        ingest.main(str(tmp_path / 'm.jsonl'), str(tmp_path / 'c.jsonl'), str(tmp_path / 'cache1'))
        ingest.main(str(tmp_path / 'm.jsonl'), str(tmp_path / 'c.jsonl'), str(tmp_path / 'cache2'))  # 캐시 없이 다시
        assert calls == [['cover', 'VRRM 40 V']]  # 두 번째는 DB에 임베딩이 있어 API를 부르지 않는다
        with psycopg.connect(url) as conn:
            counts = [conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
                      for t in ('source_documents', 'document_chunks', 'chunk_embeddings')]
        assert counts == [1, 2, 2]  # 다시 돌려도 행이 늘지 않는다
    finally:
        with psycopg.connect(base, autocommit=True) as conn:
            conn.execute(f'DROP SCHEMA {schema} CASCADE')
