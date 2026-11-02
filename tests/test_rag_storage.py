"""halfvec 전환·재적재·정확 검색 계약. TEST_DATABASE_URL은 전용 시험 DB만 사용한다."""
import json
import os
import uuid
from pathlib import Path

import numpy as np
import pytest

from backend.rag import storage
from backend.rag import ingest, retrieve
from backend.services import llm


def test_storage_type_validates_configuration(monkeypatch):
    monkeypatch.delenv('RAG_VECTOR_TYPE', raising=False)
    assert storage.vector_type() == 'vector'
    monkeypatch.setenv('RAG_VECTOR_TYPE', 'halfvec')
    assert storage.vector_type() == 'halfvec'
    monkeypatch.setenv('RAG_VECTOR_TYPE', 'halfvector')
    with pytest.raises(ValueError):
        storage.vector_type()


@pytest.fixture
def db(monkeypatch):
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('dedicated TEST_DATABASE_URL required')
    import psycopg
    from pgvector.psycopg import register_vector
    schema = 'storage_' + uuid.uuid4().hex[:10]
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute('CREATE EXTENSION IF NOT EXISTS vector')
        admin.execute(f'CREATE SCHEMA {schema}')
    scoped = url + ('&' if '?' in url else '?') + f'options=-csearch_path%3D{schema},public'
    monkeypatch.setenv('DATABASE_URL', scoped)
    monkeypatch.setenv('RAG_VECTOR_TYPE', 'vector')
    try:
        with psycopg.connect(scoped) as conn:
            register_vector(conn)
            conn.execute(Path('db/002_rag_corpus.sql').read_text())
            conn.execute("INSERT INTO source_documents (document_key,document_type,title,publisher,source_url,"
                         "file_sha256,corpus_version,collected_at,parser,chars_original,chars_kept,truncated)"
                         " VALUES ('tsc-a','DATASHEET','A','test','https://example.invalid/A.pdf',%s,'test',now(),'test',1,1,false)",
                         ('1' * 64,))
            for i in range(8):
                conn.execute('INSERT INTO document_chunks (document_id,chunk_index,content,chunk_sha256,chunker_version)'
                             ' VALUES (1,%s,%s,%s,\'test\')', (i, f'card {i}', f'{i:064x}'))
                v = np.zeros(1536, np.float32)
                v[0], v[i + 1] = 1.001, 0.2
                conn.execute('INSERT INTO chunk_embeddings (chunk_id,embedding_model,embedding) VALUES (%s,%s,%s)',
                             (i + 1, ingest.EMBED_MODEL, v))
            conn.commit()
            yield conn
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA {schema} CASCADE')


def test_compare_excludes_self_and_equal_body_and_is_read_only(db):
    db.execute('UPDATE document_chunks SET chunk_sha256=%s WHERE id=2', ('0' * 64,))
    db.commit()
    before = storage.snapshot(db)
    result = storage.compare(db, samples=3, max_seconds=20)
    assert result['queries'] == 3 and result['top5_overlap'] == 1.0
    assert all(r['query_id'] not in r['vector_top5'] + r['halfvec_top5'] for r in result['rows'])
    first = next(r for r in result['rows'] if r['query_id'] == 1)
    assert 2 not in first['vector_top5'] + first['halfvec_top5']
    assert storage.snapshot(db)['embedding_type'] == before['embedding_type'] == 'vector(1536)'


def test_halfvec_migration_binary_copy_rerun_and_dense_query(db, tmp_path, monkeypatch):
    sql = Path('db/halfvec.sql.manual').read_text()
    db.execute(sql)
    db.execute(sql)  # repeat must preserve rows and keys
    assert storage.snapshot(db)['embedding_type'] == 'halfvec(1536)'
    assert db.execute('SELECT count(*) FROM chunk_embeddings').fetchone()[0] == 8
    assert db.execute("SELECT to_regclass('ix_chunk_embeddings_hnsw')").fetchone()[0] is None
    monkeypatch.setenv('RAG_VECTOR_TYPE', 'halfvec')
    monkeypatch.setattr(llm, 'DEMO_MODE', False)
    monkeypatch.setattr(llm, 'embed_texts', lambda _: ([[1.001, 0.2] + [0.] * 1534], 0, 'test', 'test'))
    assert retrieve._dense(db, 'synthetic')[0] == 1
    db.commit()
    # Force one missing embedding, supply its existing float32 cache, forbid provider calls.
    db.execute('DELETE FROM chunk_embeddings WHERE chunk_id=8')
    db.commit()
    vec = np.zeros(1536, np.float32)
    vec[0], vec[8] = 1.001, 0.2
    ingest.VectorCache(tmp_path / 'cache').add([(f'{7:064x}', vec)])
    manifest = {'doc_id': 'tsc-a', 'title': 'A', 'manufacturer': 'test', 'source_url': 'https://example.invalid/A.pdf',
                'revision': 'test', 'usage_conditions': 'test', 'sha256': '1' * 64, 'collected_at': '2026-11-02',
                'parser': 'test', 'chars_original': 1, 'chars_kept': 1, 'truncated': False}
    (tmp_path / 'm.jsonl').write_text(json.dumps(manifest) + '\n')
    (tmp_path / 'c.jsonl').write_text(json.dumps({'doc': 'a.pdf', 'text': 'card 7', 'sha256': f'{7:064x}'}) + '\n')
    def forbidden(_):
        raise AssertionError('provider call forbidden')
    monkeypatch.setattr(llm, 'embed_texts', forbidden)
    ingest.main(str(tmp_path / 'm.jsonl'), str(tmp_path / 'c.jsonl'), str(tmp_path / 'cache'), cache_only=True)
    ingest.main(str(tmp_path / 'm.jsonl'), str(tmp_path / 'c.jsonl'), str(tmp_path / 'empty-cache'), cache_only=True)
    assert db.execute('SELECT count(*) FROM chunk_embeddings').fetchone()[0] == 8
    assert db.execute("SELECT to_regclass('ix_chunk_embeddings_hnsw')").fetchone()[0] is None


def test_halfvec_dense_keeps_query_float32_precision(db, monkeypatch):
    # Both coordinates round to 1 in half precision. Rounding the query too
    # would tie the two candidates; float32 query precision selects card 2.
    db.execute(Path('db/halfvec.sql.manual').read_text())
    db.execute('DELETE FROM chunk_embeddings WHERE chunk_id > 2')
    for cid, xy in [(1, [1., 0.]), (2, [0., 1.])]:
        db.execute('UPDATE chunk_embeddings SET embedding=%s WHERE chunk_id=%s',
                   (np.array(xy + [0.] * 1534, dtype=np.float32), cid))
    db.commit()
    monkeypatch.setenv('RAG_VECTOR_TYPE', 'halfvec')
    monkeypatch.setattr(llm, 'DEMO_MODE', False)
    monkeypatch.setattr(llm, 'embed_texts', lambda _: ([[1., 1.0002] + [0.] * 1534], 0, 'test', 'test'))
    assert retrieve._dense(db, 'precision boundary')[0] == 2


def test_compare_requires_original_vector_and_limits(db):
    with pytest.raises(ValueError):
        storage.compare(db, samples=0)
    db.execute(Path('db/halfvec.sql.manual').read_text())
    with pytest.raises(ValueError, match='vector'):
        storage.compare(db, samples=1)


def test_compare_reports_shortfall_and_time_limit(db):
    report = storage.compare(db, samples=1000, max_seconds=20)
    assert report['sample_shortfall'] == 992 and report['complete'] is False
    report = storage.compare(db, samples=1, max_seconds=1e-9)
    assert report['timed_out'] and report['queries'] == 0
    assert report['top5_overlap'] is None and report['complete'] is False


def test_compare_time_limit_includes_initial_table_lock(db):
    import psycopg
    import threading
    with psycopg.connect(db.info.dsn) as locker:
        locker.execute('LOCK TABLE chunk_embeddings IN ACCESS EXCLUSIVE MODE')
        release = threading.Timer(0.2, locker.rollback)  # a broken time bound must not hang pytest
        release.start()
        try:
            report = storage.compare(db, samples=1, max_seconds=0.02)
        finally:
            release.join()
    assert report['timed_out'] and report['queries'] == 0 and not report['complete']


def test_compare_preserves_callers_transaction_settings(db):
    before = db.execute('SHOW statement_timeout').fetchone()[0]
    index_before = db.execute('SHOW enable_indexscan').fetchone()[0]
    storage.compare(db, samples=1, max_seconds=20)
    assert db.execute('SHOW statement_timeout').fetchone()[0] == before
    assert db.execute('SHOW enable_indexscan').fetchone()[0] == index_before


def test_cache_only_ingest_rejects_missing_vector_without_provider(db, tmp_path, monkeypatch):
    db.execute('DELETE FROM chunk_embeddings WHERE chunk_id=8')
    db.commit()
    (tmp_path / 'm.jsonl').write_text('')
    (tmp_path / 'c.jsonl').write_text(json.dumps({'doc': 'a.pdf', 'text': 'card 7', 'sha256': f'{7:064x}'}) + '\n')
    def forbidden(_):
        raise AssertionError('provider call forbidden')
    monkeypatch.setattr(llm, 'embed_texts', forbidden)
    with pytest.raises(ValueError, match='cache-only'):
        ingest.main(str(tmp_path / 'm.jsonl'), str(tmp_path / 'c.jsonl'), str(tmp_path / 'cache'), cache_only=True)
    assert db.execute('SELECT count(*) FROM chunk_embeddings').fetchone()[0] == 7
