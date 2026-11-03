"""용량 예산에 맞춰 5개 다이오드 분류 문서만 골라 새 폴더에 쓰는 오프라인 도구(서버가 import하지 않는다).

- 역할: 오프라인 CLI(`python -m backend.rag.pipeline.subset`). 서버가 import하지 않는다. manifest·목록 csv·chunks.jsonl·평가 데이터셋을 모두 검증한 뒤, 분류가 CATEGORIES에 드는 문서의 manifest 줄과 카드 줄을
  <out-dir>/manifest.jsonl·chunks.jsonl로 쓰고 보고서(report.json)에 문서·카드 수, 임베딩 크기 추정(DB 행·TOAST·인덱스 제외), G3 기준 충족 여부를 담는다.
  정답(gold) PDF가 부분집합에서 빠지면 실패한다. 하나라도 어긋나면 아무것도 쓰지 않는다.
- 하지 않는 일: 입력 파일 수정, 이미 있는 폴더 덮어쓰기(out-dir은 새 폴더여야 한다), DB 접근, 임베딩. 적재는 `ingest.py`.
- 출처: docs/experiments/corpus-storage-budget.md (G3 기준), SPEC.md 6절

실행: python -m backend.rag.pipeline.subset --manifest PATH --catalog CSV --chunks PATH --dataset PATH --out-dir NEW_DIR
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlparse

CATEGORIES = frozenset({
    'Schottky Rectifier', 'Schottky Diode', 'Switching Diode',
    'Zener Diode', 'Standard Rectifier',
})
DIMENSIONS = 1536  # 임베딩 크기 추정에만 쓴다(vector는 4바이트, halfvec은 2바이트 × 차원)


def _rows(path):
    """jsonl 파일을 [(사전, 원본 바이트 줄)] 목록으로 읽는다. 객체가 아닌 줄이나 빈 파일은 ValueError."""
    # [왜] 원본 바이트 줄을 같이 들고 가야 부분집합 파일에 입력 줄을 한 글자도 바꾸지 않고 옮긴다
    rows = []
    for number, line in enumerate(Path(path).read_bytes().splitlines(keepends=True), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'{path}:{number}: expected JSON object')
        rows.append((row, line))
    if not rows:
        raise ValueError(f'{path}: empty input')
    return rows


def _filename(value):
    """값이 .pdf로 끝나는 글자인지 확인해 디렉터리를 뗀 파일 이름을 돌려준다. 아니면 ValueError."""
    if not isinstance(value, str) or not value.endswith('.pdf'):
        raise ValueError(f'Invalid PDF filename: {value!r}')
    return Path(value).name


def _manifest_filename(row):
    """manifest 줄의 PDF 파일 이름. path가 있으면 path, 없으면 source_url 끝에서 얻는다."""
    value = row.get('path')
    if not value:
        source = row.get('source_url')
        value = unquote(urlparse(source).path) if isinstance(source, str) else None
    return _filename(value)


def select_subset(manifest, catalog, chunks, dataset, out_dir):
    """입력을 모두 검증한 뒤 새 출력 폴더에 부분집합을 쓰고 보고서 사전을 돌려준다.

    입력: manifest·catalog·chunks·dataset 파일 경로, out_dir(아직 없는 폴더).
    주의: 출력 폴더가 있거나 입력을 덮을 때, 카테고리·카드·정답 PDF가 어긋날 때 ValueError. 쓰다 실패하면 폴더를 지우고 다시 올린다.
    """
    out = Path(out_dir)
    if out.exists() or out.is_symlink():
        raise ValueError('Output directory already exists')
    inputs = [Path(p).resolve(strict=True) for p in (manifest, catalog, chunks, dataset)]
    if any(not p.is_file() for p in inputs):
        raise ValueError('All inputs must be files')
    if any(out.resolve() == p or out.resolve() in p.parents for p in inputs):
        raise ValueError('Output would contain or overwrite an input')
    manifest_rows, card_rows, dataset_rows = _rows(manifest), _rows(chunks), _rows(dataset)
    with Path(catalog).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not {'file', 'categories'} <= set(reader.fieldnames or []):
            raise ValueError('Catalog requires file and categories columns')
        category_by_file = {}
        for row in reader:
            filename = _filename(row['file'])
            if filename != row['file'] or filename in category_by_file or not row['categories']:
                raise ValueError(f'Invalid or duplicate catalog row: {filename}')
            category_by_file[filename] = {v.strip() for v in row['categories'].split(';') if v.strip()}
    documents = {}
    for row, raw in manifest_rows:
        filename = _manifest_filename(row)
        if filename in documents or filename not in category_by_file:
            raise ValueError(f'Duplicate manifest or missing catalog row: {filename}')
        documents[filename] = (row, raw)
    selected = {f for f in documents if category_by_file[f] & CATEGORIES}
    coverage = set().union(*(category_by_file[f] & CATEGORIES for f in selected))
    if coverage != CATEGORIES:
        raise ValueError(f'Missing required categories: {sorted(CATEGORIES - coverage)}')
    counts, text_hashes, retained, card_keys = Counter(), set(), [], set()
    for row, raw in card_rows:
        filename = row.get('doc')
        if filename not in documents or not isinstance(row.get('text'), str) or not row['text'].strip():
            raise ValueError(f'Unknown document or invalid card text: {filename}')
        index = row.get('idx')
        if type(index) is not int or index < 0 or (filename, index) in card_keys:
            raise ValueError(f'Invalid or duplicate card index: {filename}: {index!r}')
        card_keys.add((filename, index))
        counts[filename] += 1
        if filename in selected:
            retained.append(raw)
            text_hashes.add(hashlib.sha256(row['text'].encode('utf-8')).hexdigest())
    for filename, (row, _) in documents.items():
        expected = row.get('chunks')
        if (type(expected) is not int or expected < 1 or expected != counts[filename]
                or any((filename, idx) not in card_keys for idx in range(expected))):
            raise ValueError(f'Incomplete cards: {filename}: expected {expected}, got {counts[filename]}')
    relevant_pdf_rows, circuit_only_rows, gold_files = [], [], set()
    for row, _ in dataset_rows:
        if row.get('kind') != 'relevant':
            continue
        gold = row.get('gold_chunks')
        if not isinstance(gold, list) or any(not isinstance(v, str) for v in gold):
            raise ValueError('Relevant gold_chunks must be a list of strings')
        pdfs = set()
        for value in gold:
            match = re.match(r'(.+?\.pdf)(?=\s|,|$)', value)
            if match:
                pdfs.add(_filename(match.group(1)))
        if pdfs - selected:
            raise ValueError(f'Relevant gold PDF missing from subset: {sorted(pdfs - selected)}')
        gold_files.update(pdfs)
        (relevant_pdf_rows if pdfs else circuit_only_rows).append(row.get('id'))
    selected_manifest = [raw for row, raw in manifest_rows if _manifest_filename(row) in selected]
    unique = len(text_hashes)
    report = {
        'categories': sorted(CATEGORIES), 'documents': len(selected), 'cards': len(retained),
        'distinct_text_sha256': unique, 'g3_documents_at_least_50': len(selected) >= 50,
        'g3_distinct_text_at_least_10000': unique >= 10000,
        'relevant_pdf_rows': relevant_pdf_rows, 'circuit_only_rows': circuit_only_rows,
        'retained_gold_pdfs': sorted(gold_files), 'dimensions': DIMENSIONS,
        'embedding_rows': len(retained),
        'estimated_embedding_payload_bytes': {
            'vector': len(retained) * (4 * DIMENSIONS + 8), 'halfvec': len(retained) * (2 * DIMENSIONS + 8)},
        'estimate_basis': 'one model embedding row per retained card; excludes DB/TOAST/index overhead; cache deduplication does not reduce stored rows',
        'selected_chunk_file_bytes': sum(map(len, retained)),
        'selected_text_utf8_bytes': sum(len(r['text'].encode('utf-8')) for r, _ in card_rows if r['doc'] in selected),
        'actual_database_bytes': None, 'whole_database_target_bytes': 250_000_000,
        'whole_database_target_met': None, 'retrieval_quality_measured': False,
        'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
    }
    out.mkdir()  # [왜] exist_ok 없이 만들어 이미 있는 폴더를 덮어쓰지 못하게 한다
    try:
        (out / 'manifest.jsonl').write_bytes(b''.join(selected_manifest))
        (out / 'chunks.jsonl').write_bytes(b''.join(retained))
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except BaseException:  # [왜] Ctrl-C까지 잡아야 반쯤 쓴 폴더가 남지 않는다. 지운 뒤 다시 올린다
        shutil.rmtree(out)
        raise
    return report


def main():
    """명령줄 인자를 읽어 select_subset을 돌리고 보고서를 JSON으로 출력한다. 검증 실패는 종료 코드 1."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'catalog', 'chunks', 'dataset', 'out-dir'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        report = select_subset(**vars(args))
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'Subset failed: {exc}\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
