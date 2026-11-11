"""Compose가 새 데이터베이스에 적용하는 SQL 파일 목록을 고정한다."""

from pathlib import Path


def test_compose_initdb_contains_only_current_schema():
    db_dir = Path(__file__).resolve().parents[2] / 'db'
    assert {path.name for path in db_dir.glob('*.sql')} == {
        '000_init.sql',
        '002_rag_corpus.sql',
        '008_multi_dim_embeddings.sql',
        '009_chunk_embedding_bits.sql',
        '012_document_category.sql',
        '020_service_baseline.sql',
        '026_revoke_public_grants_and_rls.sql',
    }
