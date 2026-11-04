"""문서 일부 뽑기(backend.rag.pipeline.subset) 계약: 코퍼스·API·DB 없이 오프라인으로 확인한다.

- 역할: 분류별 사본·입력 보존·관련 gold 누락·기존 출력·불완전/중복 청크 오류, 청크 수 기준 벡터 payload 추정을 확인한다.
- 하지 않는 일: subset은 적용 보류된 수동 도구라서 서비스 코퍼스를 줄이는 결정은 이 테스트가 정하지 않는다.
- 출처: evals/guides/preregister.md #10(적용 보류), SPEC 6절
"""
import csv
import hashlib
import importlib
import json

import pytest

CATEGORIES = ['Schottky Rectifier', 'Schottky Diode', 'Switching Diode', 'Zener Diode', 'Standard Rectifier']


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


@pytest.fixture
def inputs(tmp_path):
    manifest = [{'path': f'corpus/{i}.pdf', 'chunks': 1, 'doc_id': str(i)} for i in range(6)]
    cards = [{'doc': f'{i}.pdf', 'idx': 0, 'text': 'µ text' if i < 2 else str(i), 'sha256': 'untrusted'} for i in range(6)]
    catalog = [{'file': f'{i}.pdf', 'categories': CATEGORIES[i] if i < 5 else 'Bridge Rectifier'} for i in range(6)]
    paths = {k: tmp_path / f'{k}.jsonl' for k in ('manifest', 'chunks', 'dataset')}
    paths['catalog'] = tmp_path / 'catalog.csv'
    write_jsonl(paths['manifest'], manifest)
    write_jsonl(paths['chunks'], cards)
    write_jsonl(paths['dataset'], [
        {'id': 'pdf', 'kind': 'relevant', 'gold_chunks': ['0.pdf, 2쪽, table']},
        {'id': 'net', 'kind': 'relevant', 'gold_chunks': ['circuit.net, D1']},
        {'id': 'negative', 'kind': 'irrelevant', 'gold_chunks': ['missing.pdf, 1쪽']},
    ])
    with paths['catalog'].open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['file', 'categories'])
        writer.writeheader()
        writer.writerows(catalog)
    return paths


def run(inputs, out):
    return importlib.import_module('backend.rag.pipeline.subset').select_subset(**inputs, out_dir=out)


def test_selects_exact_categories_preserves_bytes_and_reports_real_counts(inputs, tmp_path):
    hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in inputs.items()}
    out = tmp_path / 'selected'
    report = run(inputs, out)
    assert {json.loads(s)['doc'] for s in (out / 'chunks.jsonl').read_text().splitlines()} == {f'{i}.pdf' for i in range(5)}
    assert (out / 'chunks.jsonl').read_bytes() == b''.join(inputs['chunks'].read_bytes().splitlines(keepends=True)[:5])
    assert (out / 'manifest.jsonl').read_bytes() == b''.join(inputs['manifest'].read_bytes().splitlines(keepends=True)[:5])
    assert hashes == {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in inputs.items()}
    assert report['documents'] == 5 and report['distinct_text_sha256'] == 4
    assert report['g3_documents_at_least_50'] is False
    assert report['g3_distinct_text_at_least_10000'] is False
    assert report['embedding_rows'] == 5
    assert report['estimated_embedding_payload_bytes'] == {'vector': 5 * (4 * 1536 + 8), 'halfvec': 5 * (2 * 1536 + 8)}
    assert report['actual_database_bytes'] is None and report['whole_database_target_met'] is None
    assert report['relevant_pdf_rows'] == ['pdf'] and report['circuit_only_rows'] == ['net']
    assert json.loads((out / 'report.json').read_text()) == report


@pytest.mark.parametrize('failure', ['missing_catalog', 'category', 'incomplete', 'missing_gold', 'unknown_card'])
def test_invalid_inputs_fail_without_output(inputs, tmp_path, failure):
    if failure in ('missing_catalog', 'category'):
        rows = list(csv.DictReader(inputs['catalog'].open()))
        if failure == 'missing_catalog':
            rows.pop()
        else:
            rows[0]['categories'] = 'Schottky Rectifier TYPO'
        with inputs['catalog'].open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['file', 'categories'])
            writer.writeheader()
            writer.writerows(rows)
    elif failure == 'incomplete':
        inputs['chunks'].write_text('\n'.join(inputs['chunks'].read_text().splitlines()[1:]) + '\n')
    elif failure == 'unknown_card':
        with inputs['chunks'].open('a') as stream:
            stream.write(json.dumps({'doc': 'unknown.pdf', 'text': 'x'}) + '\n')
    else:
        write_jsonl(inputs['dataset'], [{'id': 'gold', 'kind': 'relevant', 'gold_chunks': ['5.pdf, 1쪽']}])
    out = tmp_path / 'selected'
    with pytest.raises(ValueError):
        run(inputs, out)
    assert not out.exists()


def test_existing_output_is_untouched(inputs, tmp_path):
    out = tmp_path / 'existing'
    out.mkdir()
    marker = out / 'keep'
    marker.write_text('keep')
    with pytest.raises(ValueError, match='exist'):
        run(inputs, out)
    assert marker.read_text() == 'keep'


def test_input_path_cannot_be_output(inputs):
    before = inputs['manifest'].read_bytes()
    with pytest.raises(ValueError):
        run(inputs, inputs['manifest'])
    assert inputs['manifest'].read_bytes() == before


def test_pdf_gold_without_page_comma_cannot_be_silently_skipped(inputs, tmp_path):
    write_jsonl(inputs['dataset'], [{'id': 'gold', 'kind': 'relevant', 'gold_chunks': ['missing.pdf table row']}])
    with pytest.raises(ValueError, match='gold PDF'):
        run(inputs, tmp_path / 'selected')


def test_duplicate_card_keys_cannot_replace_missing_cards(inputs, tmp_path):
    manifests = [json.loads(v) for v in inputs['manifest'].read_text().splitlines()]
    manifests[0]['chunks'] = 2
    write_jsonl(inputs['manifest'], manifests)
    rows = [json.loads(v) for v in inputs['chunks'].read_text().splitlines()]
    write_jsonl(inputs['chunks'], [*rows, rows[0]])
    with pytest.raises(ValueError, match='card index'):
        run(inputs, tmp_path / 'selected')
    assert not (tmp_path / 'selected').exists()


@pytest.mark.parametrize('index', [None, -1, '0', True])
def test_card_index_must_be_nonnegative_integer(inputs, tmp_path, index):
    rows = [json.loads(v) for v in inputs['chunks'].read_text().splitlines()]
    rows[0]['idx'] = index
    write_jsonl(inputs['chunks'], rows)
    with pytest.raises(ValueError, match='card index'):
        run(inputs, tmp_path / 'selected')


@pytest.mark.parametrize('declared', ['missing', None, 0, True])
def test_manifest_requires_positive_integer_card_count(inputs, tmp_path, declared):
    rows = [json.loads(v) for v in inputs['manifest'].read_text().splitlines()]
    if declared == 'missing':
        rows[0].pop('chunks')
    else:
        rows[0]['chunks'] = declared
    write_jsonl(inputs['manifest'], rows)
    with pytest.raises(ValueError, match='Incomplete cards'):
        run(inputs, tmp_path / 'selected')
    assert not (tmp_path / 'selected').exists()


def test_card_indices_must_cover_declared_range(inputs, tmp_path):
    rows = [json.loads(v) for v in inputs['chunks'].read_text().splitlines()]
    rows[0]['idx'] = 7
    write_jsonl(inputs['chunks'], rows)
    with pytest.raises(ValueError, match='Incomplete cards'):
        run(inputs, tmp_path / 'selected')
    assert not (tmp_path / 'selected').exists()


def test_compact_manifest_uses_decoded_source_url_and_preserves_lines(inputs, tmp_path):
    manifests = [json.loads(v) for v in inputs['manifest'].read_text().splitlines()]
    for i, row in enumerate(manifests):
        row.pop('path')
        row['source_url'] = f'https://example.invalid/pdf/{i}.pdf'
    manifests[0]['source_url'] = 'https://example.invalid/pdf/0%20series.pdf?download=1'
    write_jsonl(inputs['manifest'], manifests)
    cards = inputs['chunks'].read_text().replace('0.pdf', '0 series.pdf')
    inputs['chunks'].write_text(cards)
    inputs['catalog'].write_text(inputs['catalog'].read_text().replace('0.pdf', '0 series.pdf'))
    inputs['dataset'].write_text(
        inputs['dataset'].read_text(encoding='utf-8').replace('0.pdf', '0 series.pdf'),
        encoding='utf-8',
    )
    before = inputs['manifest'].read_bytes()
    out = tmp_path / 'selected'
    report = run(inputs, out)
    assert report['documents'] == 5 and report['retained_gold_pdfs'] == ['0 series.pdf']
    assert (out / 'manifest.jsonl').read_bytes() == b''.join(before.splitlines(keepends=True)[:5])
    assert inputs['manifest'].read_bytes() == before


@pytest.mark.parametrize('fields', [{}, {'path': ''}, {'source_url': ''}, {'path': None, 'source_url': ''}])
def test_manifest_without_filename_source_fails(inputs, tmp_path, fields):
    rows = [json.loads(v) for v in inputs['manifest'].read_text().splitlines()]
    rows[0].pop('path')
    rows[0].update(fields)
    write_jsonl(inputs['manifest'], rows)
    with pytest.raises(ValueError, match='Invalid PDF filename'):
        run(inputs, tmp_path / 'selected')
    assert not (tmp_path / 'selected').exists()
