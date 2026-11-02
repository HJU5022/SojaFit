"""Offline, non-destructive corpus selection; see corpus-storage-budget.md.

Run with --manifest PATH --catalog CSV --chunks PATH --dataset PATH
--out-dir NEW_DIR. Payload estimates exclude PostgreSQL rows, TOAST and indexes.
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
DIMENSIONS = 1536


def _rows(path):
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
    if not isinstance(value, str) or not value.endswith('.pdf'):
        raise ValueError(f'Invalid PDF filename: {value!r}')
    return Path(value).name


def _manifest_filename(row):
    value = row.get('path')
    if not value:
        source = row.get('source_url')
        value = unquote(urlparse(source).path) if isinstance(source, str) else None
    return _filename(value)


def select_subset(manifest, catalog, chunks, dataset, out_dir):
    """Validate all inputs before publishing a new output directory; return report."""
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
    out.mkdir()  # Exclusive creation: an existing directory is never replaced.
    try:
        (out / 'manifest.jsonl').write_bytes(b''.join(selected_manifest))
        (out / 'chunks.jsonl').write_bytes(b''.join(retained))
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except BaseException:
        shutil.rmtree(out)
        raise
    return report


def main():
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
