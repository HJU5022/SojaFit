"""부품 사양 표 DB: db/011 SQL, 적재(`specs load`), 조회(`backend.rag.spec_lookup`)를 작은 가짜 사양 파일로 확인한다.

- 역할: SQL을 두 번 적용해도 행·인덱스가 그대로인지, 나쁜 행(없는 코드·단위, 값 없음, 원문 없음, 없는 문서)을 막는지,
  적재가 문서 단위로 바꿔 넣어 다시 돌려도 같은지·모르는 문서는 건너뛰는지·`--docs`로 한 문서만 바꾸는지,
  `part_specs`(대소문자 무시, 코드 거르기, 인용)와 `find_candidates`(이상·이하, 자리, 제너 VZ 창, 패키지·분류 거르기, 개수 제한)를 본다.
- 하지 않는 일: 실제 코퍼스 적재와 응답 시간은 보지 않는다(작업 기록에 실측을 남긴다). TEST_DATABASE_URL을 줄 때만 돈다(CI에는 DB가 없다).
  임시 스키마를 만들고 끝나면 지운다.
- 출처: db/schema/table-definition.md 5.7, ADR 0013, ADR 0007(문서 단위 증분)
- [주의] DATABASE_URL은 .env의 서비스 DB(Supabase)를 가리킬 수 있어 쓰지 않는다. 로컬 compose DB 주소만 TEST_DATABASE_URL로 준다.
"""
import json
import os
import uuid

import pytest

from backend.rag import spec_lookup
from backend.rag.pipeline import specs
from backend.rag.pipeline.chunk import doc_key

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='TEST_DATABASE_URL을 줄 때만 돈다')

RECT, ZEN, NOPE = 'SS32 SERIES_Q2412.pdf', 'BZT52 SERIES_G1804.pdf', 'NOPE SERIES_Z0000.pdf'


def spec(part, doc, code, slot, value, unit, family='schottky-rectifier', idx=3):
    """specs build가 쓰는 part_specifications.jsonl 한 줄 모양(칸 하나 = 줄 하나)."""
    r = {'doc': doc, 'family': family, 'symbol': code, 'test_condition': None, 'page_number': 2, 'table_name': 'ELEC',
         'row_label': part, 'text_value': None, 'footnote_text': None, 'chunk': {'doc': doc, 'idx': idx}, 'part': part,
         'parameter_code': code, 'minimum_value': None, 'typical_value': None, 'maximum_value': None,
         'source_value_text': f'{value} {unit}', 'source_unit': unit, 'normalized_unit': unit, 'source_level': 'part',
         'checks': {'value_in_source': True, 'plausible': True}}
    r[{'min': 'minimum_value', 'typ': 'typical_value', 'max': 'maximum_value'}[slot]] = value
    return r


ROWS = [
    spec('SS34', RECT, 'VRRM', 'max', 40.0, 'V'), spec('SS34', RECT, 'IF_AV', 'max', 3.0, 'A'),
    # [왜] 200 µA를 SI로 바꾸면 float가 0.00019999999999999998이 된다. DB에는 0.0002로 들어가야 한다
    spec('SS34', RECT, 'IR', 'max', 0.00019999999999999998, 'A'),
    spec('SS36', RECT, 'VRRM', 'max', 60.0, 'V'), spec('SS36', RECT, 'IF_AV', 'max', 3.0, 'A'),
    spec('SS32', RECT, 'VRRM', 'max', 20.0, 'V'), spec('SS32', RECT, 'IF_AV', 'max', 3.0, 'A'),
    spec('BZT52C3V6', ZEN, 'VZ', 'min', 3.42, 'V', 'zener-diode'), spec('BZT52C3V6', ZEN, 'VZ', 'max', 3.78, 'V', 'zener-diode'),
    spec('BZT52C3V9', ZEN, 'VZ', 'min', 3.7, 'V', 'zener-diode'), spec('BZT52C3V9', ZEN, 'VZ', 'max', 4.1, 'V', 'zener-diode'),
    spec('BZT52C3V3', ZEN, 'VZ', 'min', 3.1, 'V', 'zener-diode'), spec('BZT52C3V3', ZEN, 'VZ', 'max', 3.5, 'V', 'zener-diode'),
    spec('BZT52C3V6X', ZEN, 'VZ', 'min', 3.5, 'V', 'zener-diode'),  # 최대 행이 없어 창 조건을 다 채우지 못한다
    spec('NOPE1', NOPE, 'VRRM', 'max', 40.0, 'V'),  # DB에 없는 문서
]
PACKAGES = [
    {'part': 'SS34', 'doc': RECT, 'family': 'schottky-rectifier', 'packages': ['SMA', 'DO-214AC']},
    {'part': 'SS36', 'doc': RECT, 'family': 'schottky-rectifier', 'packages': ['SMB']},
    {'part': 'SS32', 'doc': RECT, 'family': 'schottky-rectifier', 'packages': ['SMAF']},
    {'part': 'BZT52C3V6', 'doc': ZEN, 'family': 'zener-diode', 'packages': ['SOD-123']},
]


def write_specs(folder, rows=ROWS, packages=PACKAGES):
    folder.mkdir(exist_ok=True)
    (folder / 'part_specifications.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    (folder / 'packages.jsonl').write_text(''.join(json.dumps(p) + '\n' for p in packages), encoding='utf-8')
    return folder


@pytest.fixture
def url():
    """임시 스키마에 002·011을 적용하고 문서 두 건(RECT, ZEN)을 넣은 접속 주소. 끝나면 스키마를 지운다."""
    import psycopg
    base, schema = os.environ['TEST_DATABASE_URL'], f'test_specs_{uuid.uuid4().hex[:8]}'
    url = base + ('&' if '?' in base else '?') + f'options=-csearch_path%3D{schema},public'
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA {schema}')
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            for sql in ('db/002_rag_corpus.sql', 'db/011_part_specifications.sql'):
                conn.execute(open(sql, encoding='utf-8').read())
            for n, file in enumerate((RECT, ZEN), 1):
                conn.execute("INSERT INTO source_documents (document_key, document_type, title, publisher, source_url,"
                             " file_sha256, corpus_version, collected_at, parser, chars_original, chars_kept, truncated)"
                             " VALUES (%s, 'DATASHEET', %s, 'TSC', %s, %s, 't', now(), 'p', 1, 1, false)",
                             (doc_key(file), file[:-4], f'https://example.test/datasheet/{file}', str(n) * 64))
        yield url
    finally:
        with psycopg.connect(base, autocommit=True) as conn:
            conn.execute(f'DROP SCHEMA {schema} CASCADE')


def ids(url, doc):
    import psycopg
    with psycopg.connect(url) as conn:
        return [r[0] for r in conn.execute('SELECT s.id FROM part_specifications s JOIN source_documents d ON d.id = s.document_id'
                                           ' WHERE d.document_key = %s ORDER BY s.id', (doc_key(doc),))]


# --- db/011 SQL ---

def test_sql_applies_twice_without_change(url):
    """두 번째 적용은 있는 행·제약·인덱스를 건드리지 않는다."""
    import psycopg
    with psycopg.connect(url, autocommit=True) as conn:
        doc = conn.execute('SELECT min(id) FROM source_documents').fetchone()[0]
        conn.execute("INSERT INTO part_specifications (part_number, document_id, parameter_code, maximum_value, source_value_text)"
                     " VALUES ('SS34', %s, 'VRRM', 40, '40 V')", (doc,))
        catalog = ("SELECT array_agg(c.conname || pg_get_constraintdef(c.oid) ORDER BY c.conname) FROM pg_constraint c"
                   " WHERE c.conrelid = 'part_specifications'::regclass")
        # [주의] 시험 DB의 public에도 같은 이름 표가 있을 수 있어 임시 스키마(current_schema)만 센다
        index = ("SELECT array_agg(indexname ORDER BY indexname) FROM pg_indexes"
                 " WHERE schemaname = current_schema() AND tablename = 'part_specifications'")
        before = conn.execute(catalog).fetchone()[0], conn.execute(index).fetchone()[0]
        conn.execute(open('db/011_part_specifications.sql', encoding='utf-8').read())
        after = conn.execute(catalog).fetchone()[0], conn.execute(index).fetchone()[0]
        assert conn.execute('SELECT count(*) FROM part_specifications').fetchone()[0] == 1
    assert before == after and len(after[1]) == 4  # pk + upper(part_number) + parameter_code + document_id


@pytest.mark.parametrize('change', [
    {'parameter_code': 'VRMS'},                       # 18개 코드 밖
    {'normalized_unit': 'mA'},                        # SI 기본 단위 밖
    {'maximum_value': None},                          # 최소·대표·최대·글 값이 모두 비었다
    {'source_value_text': None},                      # 원문 표기는 꼭 있어야 한다
    {'document_id': 999999},                          # 없는 문서
])
def test_sql_rejects_bad_rows(url, change):
    import psycopg
    with psycopg.connect(url, autocommit=True) as conn:
        good = {'part_number': 'SS34', 'document_id': conn.execute('SELECT min(id) FROM source_documents').fetchone()[0],
                'parameter_code': 'VRRM', 'maximum_value': 40, 'normalized_unit': 'V', 'source_value_text': '40 V'}
        insert = 'INSERT INTO part_specifications ({}) VALUES ({})'
        conn.execute(insert.format(', '.join(good), ', '.join(['%s'] * len(good))), list(good.values()))  # 바꾸기 전 행은 들어간다
        bad = {**good, **change}
        with pytest.raises(psycopg.errors.IntegrityError):
            conn.execute(insert.format(', '.join(bad), ', '.join(['%s'] * len(bad))), list(bad.values()))


# --- 적재(specs load) ---

def test_load_is_idempotent_and_skips_unknown_docs(url, tmp_path, capsys):
    """다시 적재해도 행 수가 같고(문서 단위로 지우고 다시 넣는다), DB에 없는 문서는 세어서 건너뛴다."""
    folder = write_specs(tmp_path / 'specs')
    first = specs.load(folder, url)
    old = ids(url, RECT)
    second = specs.load(folder, url)
    assert first == second
    assert first['missing_docs'] == [NOPE] and first['docs'] == 2
    # 숫자 14줄(NOPE 문서 1줄 제외) + 패키지 5줄
    assert first['rows_by_code'] == {'VRRM': 3, 'IF_AV': 3, 'IR': 1, 'VZ': 7, 'PACKAGE': 5}
    assert ids(url, RECT) and set(ids(url, RECT)).isdisjoint(old)  # 같은 수지만 새로 넣은 행이다
    assert 'NOPE SERIES_Z0000.pdf' in capsys.readouterr().out


def test_load_docs_replaces_only_named_document(url, tmp_path):
    """`--docs`로 준 문서만 지우고 다시 넣는다. 다른 문서 행은 그대로다(새·고친 데이터시트 하나만 다시 적재)."""
    specs.load(write_specs(tmp_path / 'a'), url)
    zen = ids(url, ZEN)
    folder = write_specs(tmp_path / 'b', [r for r in ROWS if r['part'] != 'SS36'],
                         [p for p in PACKAGES if p['part'] != 'SS36'])
    specs.main(['load', str(folder), '--dsn', url, '--docs', RECT])
    assert ids(url, ZEN) == zen
    import psycopg
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT count(*) FROM part_specifications WHERE part_number = 'SS36'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM part_specifications WHERE part_number = 'SS34'").fetchone()[0] == 5


# --- 조회(spec_lookup) ---

@pytest.fixture
def conn(url, tmp_path):
    import psycopg
    specs.load(write_specs(tmp_path / 'specs'), url)
    with psycopg.connect(url) as conn:
        yield conn


def test_part_specs_case_insensitive_with_citation(conn):
    rows = spec_lookup.part_specs(conn, 'ss34')
    assert [(r['code'], r['max']) for r in rows] == [('IF_AV', 3.0), ('IR', 0.0002), ('PACKAGE', None), ('PACKAGE', None),
                                                      ('VRRM', 40.0)]
    vrrm = rows[-1]
    assert vrrm['part'] == 'SS34' and vrrm['unit'] == 'V' and vrrm['source_value_text'] == '40.0 V'
    assert vrrm['citation'] == {'document': RECT, 'page': 2, 'table': 'ELEC', 'row': 'SS34', 'chunk_index': 3}
    assert [r['text'] for r in rows if r['code'] == 'PACKAGE'] == ['SMA', 'DO-214AC']
    assert [r['code'] for r in spec_lookup.part_specs(conn, 'SS34', ['VRRM'])] == ['VRRM']
    assert spec_lookup.part_specs(conn, 'NOPE1') == []  # 건너뛴 문서의 품번은 없다


def test_find_candidates_ratings_and_package(conn):
    """VRRM ≥ 40 V, IF_AV ≥ 1 A(자리 없으면 최대). 패키지는 대소문자 무시 부분 일치(SMA는 SMAF에도 걸린다)."""
    cond = [{'code': 'VRRM', 'gte': 40}, {'code': 'IF_AV', 'gte': 1.0}]
    assert [p['part'] for p in spec_lookup.find_candidates(conn, cond)] == ['SS34', 'SS36']
    found = spec_lookup.find_candidates(conn, cond, package='sma')
    assert [p['part'] for p in found] == ['SS34']
    assert found[0]['category'] == 'schottky-rectifier' and found[0]['packages'] == ['SMA', 'DO-214AC']
    assert sorted(m['code'] for m in found[0]['matches']) == ['IF_AV', 'VRRM']
    assert found[0]['matches'][0]['citation']['document'] == RECT
    assert spec_lookup.find_candidates(conn, cond, category='zener-diode') == []
    assert [p['part'] for p in spec_lookup.find_candidates(conn, cond, limit=1)] == ['SS34']
    assert [p['part'] for p in spec_lookup.find_candidates(conn, [{'code': 'VRRM', 'lte': 20}])] == ['SS32']


def test_find_candidates_zener_window(conn):
    """VZ 최소 ≥ 3.42 그리고 VZ 최대 ≤ 3.78(경계 포함). 각 조건은 그 품번의 행 하나 이상이 채우면 된다."""
    cond = [{'code': 'VZ', 'slot': 'min', 'gte': 3.42}, {'code': 'VZ', 'slot': 'max', 'lte': 3.78}]
    found = spec_lookup.find_candidates(conn, cond, category='zener-diode')
    assert [p['part'] for p in found] == ['BZT52C3V6']
    assert [(m['min'], m['max']) for m in found[0]['matches']] == [(3.42, None), (None, 3.78)]  # 넣은 순서(코드·id 순)
