"""데이터시트 서재 API(`GET /api/datasheets`, #67) 시험.

- 역할: 로그인 필요(401), 표지 품번 · 제목 · 제조사 부분 일치(대소문자 무시, %·_는 글자 그대로), 분류 거르기, 50건 쪽 나눔과 쪽과 상관없는 전체 수,
  폐기 문서 숨김(목록 · 분류 수 모두), 표지 청크가 없는 문서의 빈 품번 목록, 쪽 번호 422.
- DB 시험은 TEST_AUTH_DATABASE_URL이 있을 때만 격리 스키마에서 돈다. 코퍼스 표는 db/002 · 012 SQL을 그대로 쓰되
  chunk_embeddings(pgvector) 앞까지만 만든다(CI의 postgres:16에는 pgvector가 없다).
- 출처: SPEC.md 4절, backend/api/datasheets.py.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from backend import auth
from backend.main import app

DB_DIR = Path(__file__).resolve().parents[2] / 'db'
CORPUS_SQL = (DB_DIR / '002_rag_corpus.sql').read_text(encoding='utf-8').split('CREATE TABLE IF NOT EXISTS chunk_embeddings')[0] \
    + (DB_DIR / '012_document_category.sql').read_text(encoding='utf-8')
SS32_PARTS = ['SS32', 'SS33', 'SS34', 'SS35', 'SS36']
# (제목, 분류, 폐기 여부, 표지 품번). 제너 54건은 표지 없이 쪽 나눔만 본다
DOCS = [('SS32 SERIES', 'schottky-rectifier', False, SS32_PARTS), ('1N4148W SERIES', 'switching-diode', False, ['1N4148W']),
        ('SS34 OLD', 'tvs', True, ['SS34']), *((f'Z{i:03} SERIES', 'zener-diode', False, None) for i in range(54))]


def test_datasheets_require_session():
    response = TestClient(app).get('/api/datasheets?q=SS34')
    assert response.status_code == 401 and response.json()['error']['code'] == 'UNAUTHORIZED'


@pytest.fixture
def library(monkeypatch):
    url = os.getenv('TEST_AUTH_DATABASE_URL')
    if not url:
        pytest.skip('requires an isolated test database')
    schema = 'datasheets_api_' + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {} AUTHORIZATION CURRENT_USER').format(sql.Identifier(schema)))
        connect = lambda: psycopg.connect(url, options=f'-csearch_path={schema}')
        monkeypatch.setattr(auth, 'connection', connect)
        try:
            with connect() as conn:
                conn.execute(CORPUS_SQL)
                for i, (title, category, retired, parts) in enumerate(DOCS):
                    doc = conn.execute(
                        'INSERT INTO source_documents (document_key, document_type, title, publisher, source_url, revision, file_sha256, corpus_version,'
                        ' collected_at, parser, chars_original, chars_kept, truncated, category, retired_at)'
                        " VALUES (%s, 'DATASHEET', %s, 'Taiwan Semiconductor', %s, 'A2104', %s, 'v1', %s, 'docling', 1, 1, false, %s, %s) RETURNING id",
                        (f'doc-{i}', title, f'https://services.example/{title}_A2104.pdf', f'{i:064d}', datetime(2026, 11, 1, tzinfo=timezone.utc),
                         category, datetime(2026, 11, 2, tzinfo=timezone.utc) if retired else None)).fetchone()[0]
                    if parts:
                        conn.execute("INSERT INTO document_chunks (document_id, chunk_index, content, chunk_sha256, chunker_version) VALUES (%s, 0, %s, %s, 'v4')",
                                     (doc, f'[{title}_A2104.pdf] 이 데이터시트의 품번: ' + ', '.join(parts), f'{i:064d}'))
            app.dependency_overrides[auth.current_user_id] = lambda: 1
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def search(client, **params):
    response = client.get('/api/datasheets', params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_part_number_finds_its_series_and_retired_rows_stay_hidden(library):
    found = search(library, q=' ss34 ')
    assert found['total'] == 1  # 폐기한 "SS34 OLD"는 표지에 SS34가 있어도 나오지 않는다
    (item,) = found['items']
    assert set(item) == {'id', 'title', 'publisher', 'revision', 'category', 'source_url', 'collected_at', 'parts'}
    assert (item['title'], item['category'], item['revision'], item['parts']) == ('SS32 SERIES', 'schottky-rectifier', 'A2104', SS32_PARTS)
    assert search(library, q='1n4148w')['items'][0]['title'] == '1N4148W SERIES'
    assert search(library, q='TAIWAN semi')['total'] == 56  # 제조사도 대소문자 무시
    assert search(library, q='z053 series')['items'][0]['parts'] == []  # 표지 청크가 없는 문서
    assert search(library, q='%')['total'] == search(library, q='_')['total'] == 0  # 와일드카드가 아니라 글자
    assert search(library, q='데이터시트')['total'] == 0  # 표지의 고정 문구는 검색 대상이 아니다


def test_category_filter_pages_and_counts(library):
    first = search(library, category='zener-diode')
    assert (first['total'], first['page'], first['page_size'], len(first['items'])) == (54, 1, 50, 50)
    assert [i['title'] for i in first['items'][:2]] == ['Z000 SERIES', 'Z001 SERIES']  # 제목 순
    second = search(library, category='zener-diode', page=2)
    assert (second['total'], [i['title'] for i in second['items']]) == (54, ['Z050 SERIES', 'Z051 SERIES', 'Z052 SERIES', 'Z053 SERIES'])
    beyond = search(library, category='zener-diode', page=3)
    assert (beyond['items'], beyond['total']) == ([], 54)  # 범위 밖 쪽(깊은 링크)도 전체 수는 그대로
    assert search(library, q='ss34', category='zener-diode')['total'] == 0
    assert search(library, category='tvs')['total'] == 0  # 폐기 문서뿐인 분류
    # 분류 수는 서재 전체(폐기 제외)이고 검색어와 상관없다. 많은 순, 같으면 이름 순
    assert search(library, q='ss34')['categories'] == [{'category': 'zener-diode', 'count': 54}, {'category': 'schottky-rectifier', 'count': 1},
                                                       {'category': 'switching-diode', 'count': 1}]


@pytest.mark.parametrize('params', [{'page': 0}, {'page': 1001}, {'q': 'x' * 101}])
def test_out_of_range_input_is_422(params):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    try:
        response = TestClient(app).get('/api/datasheets', params=params)  # DB를 열기 전에 거른다
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422 and response.json()['error']['code'] == 'VALIDATION_ERROR'
