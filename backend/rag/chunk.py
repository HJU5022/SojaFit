"""Docling 파싱 결과를 검색 카드로 자르고 문서 목록(manifest)을 쓴다(오프라인 도구).

- 역할: 오프라인 CLI(`python -m backend.rag.chunk`). 서버가 import하지 않는다.
  - PDF마다 카드: 품번 표지 1장 + 표 밖 글(Docling HybridChunker, 표가 든 조각은 뺌) + 표 한 행 = 한 장.
    표 카드는 합친 칸을 걸친 모든 자리에 채우고 앞에 [파일 · 쪽 · 표 제목] 이름표를 붙인다.
  - <출력>/chunks.jsonl(카드 한 장 = 한 줄), <출력>/summary.json(카드 수, 서로 다른 본문 수), manifest.jsonl(문서 한 개 = 한 줄)
  - manifest에는 문서마다 다른 값만 쓴다. 모든 문서에 같은 값은 DOC_DEFAULTS에 두고 ingest.py가 읽을 때 채운다.
- 하지 않는 일: 임베딩·DB 적재(`ingest.py`), 파싱(`parse.py`). 단 `doc_key`·`DOC_DEFAULTS`·`CHUNKER_VERSION`은 `ingest.py`가 import해 쓴다.
- 출처: docs/specs/rag-pipeline.md What 4·AC-01~03·EC-03, EVAL_REPORT.md 1장 청킹 비교(개선 2)
- 의존성: 표 카드 함수는 표준 라이브러리만 쓴다. 실행(main)에는 uv 그룹 ingest(docling)가 필요하다.

실행: uv run --group ingest python -m backend.rag.chunk <docling json 폴더> <목록 csv> <pdf 폴더> <출력 폴더> <manifest.jsonl>
"""
import csv
import hashlib
import json
import os
import re
import sys

CHUNKER_VERSION = 'tsc-cards-2026-11-01'  # document_chunks.chunker_version에 들어가는 규칙 이름
PARSER = 'docling 2.145.0 (OCR off)'
USAGE = 'See data/corpus/CORPUS.md; informational/non-commercial, unmodified PDF, notices retained and source attributed.'
# [왜] 1,360줄에 같은 값을 되풀이하면 manifest가 1MB를 넘어 Checkpoint 대시보드가 읽지 못한다(512,000바이트 아래로 둔다).
# [주의] 이 값과 다른 문서(다른 제조사, 인젝션 시험 문서)는 manifest 줄에 그 키를 적으면 줄의 값이 앞선다.
DOC_DEFAULTS = {'manufacturer': 'Taiwan Semiconductor', 'collected_at': '2026-11-01', 'parser': PARSER,
                'status': 'parsed_chunked', 'purpose': 'corpus', 'usage_conditions': USAGE}


def sha(text):
    """글자의 sha256 16진 문자열(카드 본문 해시, chunk_sha256)."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def doc_key(file):
    """'1N4148 SERIES_K2301.pdf' → 'tsc-1n4148-series_k2301' (manifest doc_id, DB document_key)."""
    return 'tsc-' + file[:-4].lower().replace(' ', '-')


def revision(file):
    """파일 이름 끝의 개정판 코드(예: '..._H2104.pdf' → 'H2104')."""
    m = re.search(r'_([A-Z]\d{4})\.pdf$', file)
    return m.group(1) if m else None


def table_cards(file, page, n_rows, n_cols, cells):
    """표 하나를 데이터 행마다 카드 한 장으로 만든다(AC-01·AC-02)."""
    # cells: (시작 행, 끝 행, 시작 열, 끝 열, 글자, 머리 칸 여부) 목록. 끝은 포함하지 않는다(Docling offset과 같음)
    if not n_rows or not n_cols:  # [주의] Docling이 칸 없는 빈 표를 낼 때가 있다(EC-03). 건너뛴다
        return []
    grid = [[''] * n_cols for _ in range(n_rows)]
    is_head = [False] * n_rows
    for r0, r1, c0, c1, text, head in cells:
        for r in range(r0, r1):  # [왜] 합친 칸은 한 자리에만 글자가 있어서, 걸친 모든 자리에 같은 글자를 채운다
            for k in range(c0, c1):
                grid[r][k] = text.strip()
            is_head[r] = is_head[r] or head
    heads = [r for r in range(n_rows) if is_head[r]] or [0]  # 머리 행 표시가 없으면 첫 행을 머리로 본다
    names = []  # 열 이름 = 그 열의 머리 행 글자들을 ' / '로 이은 것(같은 글자는 한 번만)
    for k in range(n_cols):
        parts = []
        for r in heads:
            if grid[r][k] and grid[r][k] not in parts:
                parts.append(grid[r][k])
        names.append(' / '.join(parts) or f'열{k + 1}')
    title = grid[heads[0]][0]
    out = []
    for r in range(n_rows):
        if is_head[r] or not any(grid[r]):
            continue
        cells_text = ' | '.join(f'{names[k]}: {grid[r][k]}' for k in range(n_cols) if grid[r][k])
        out.append({'kind': 'table_row', 'page': page, 'table': title, 'row': next(v for v in grid[r] if v),
                    'text': f'[{file} · {page}쪽 · {title}] {cells_text}'})
    return out


def doc_cards(doc, file, parts, chunker):
    """Docling 문서 하나를 (카드 목록: 표지·표 밖 글·표 행 순서, 원문 글자 수, 카드에 들어간 원문 글자 수)로 바꾼다."""
    from docling_core.types.doc import TableItem, TextItem
    cards = [{'kind': 'cover', 'page': None, 'table': None, 'row': None,
              'text': f'[{file}] 이 데이터시트의 품번: {", ".join(parts)}'}]
    kept_refs, headings = set(), set()  # 글 카드에 들어간 원문 글 조각, 카드 앞에 붙은 제목
    for c in chunker.chunk(doc):
        if any(isinstance(it, TableItem) for it in c.meta.doc_items):  # 표는 아래에서 행 단위로 따로 만든다
            continue
        kept_refs.update(it.self_ref for it in c.meta.doc_items)
        headings.update(c.meta.headings or [])  # [왜] 소제목은 doc_items가 아니라 contextualize가 카드 앞에 붙인다
        prov = c.meta.doc_items[0].prov if c.meta.doc_items else []
        cards.append({'kind': 'text', 'page': prov[0].page_no if prov else None, 'table': None, 'row': None,
                      'text': chunker.contextualize(c)})  # contextualize는 조각 앞에 소속 제목을 붙인다
    kept_tables = []
    for t in doc.tables:
        cells = [(c.start_row_offset_idx, c.end_row_offset_idx, c.start_col_offset_idx, c.end_col_offset_idx,
                  c.text, c.column_header) for c in t.data.table_cells]
        rows = table_cards(file, t.prov[0].page_no if t.prov else None, t.data.num_rows, t.data.num_cols, cells)
        cards += rows
        if rows:
            kept_tables.append(t.self_ref)
    # 원문 글자 수 = 본문(머리글·바닥글 제외) 글 조각 + 표 칸. 카드에 들어간 글자 수 = 글 카드에 든 조각 + 카드를 만든 표의 칸
    # [왜] 이름표·표지·반복되는 열 이름은 원문이 아니라 세지 않는다. 표가 섞여 건너뛴 글 조각은 빠진 것으로 센다
    body = [it for it, _ in doc.iterate_items()]
    texts = [it for it in body if isinstance(it, TextItem)]
    tables = [it for it in body if isinstance(it, TableItem)]
    table_chars = {t.self_ref: sum(len(c.text) for c in t.data.table_cells) for t in tables}
    original = sum(len(it.text) for it in texts) + sum(table_chars.values())
    kept = sum(len(it.text) for it in texts if it.self_ref in kept_refs or it.text in headings) + \
        sum(table_chars.get(r, 0) for r in kept_tables)
    return cards, original, kept


def main(json_dir, list_csv, pdf_dir, out_dir, manifest_path):
    """Docling json 폴더를 카드(chunks.jsonl)와 문서 목록(manifest.jsonl)으로 바꾸고 summary.json을 쓴다."""
    # json_dir: parse.py 결과, list_csv: collect.py list 결과, pdf_dir: 원본 PDF(sha256 계산용)
    # [주의] 목록 csv에 없는 PDF가 json 폴더에 있으면 meta[...]에서 KeyError로 멈춘다(조용히 건너뛰지 않는다)
    from docling.chunking import HybridChunker
    from docling_core.types.doc import DoclingDocument
    with open(list_csv, encoding='utf-8') as fh:
        meta = {r['file']: r for r in csv.DictReader(fh)}
    chunker = HybridChunker()  # 기본 토크나이저(all-MiniLM-L6-v2) 길이 기준으로 자른다
    os.makedirs(out_dir, exist_ok=True)
    n_cards, seen = 0, set()
    with open(os.path.join(out_dir, 'chunks.jsonl'), 'w', encoding='utf-8') as fc, \
            open(manifest_path, 'w', encoding='utf-8') as fm:
        for f in sorted(x for x in os.listdir(json_dir) if x.endswith('.json')):
            file, m = f[:-5], meta[f[:-5]]
            doc = DoclingDocument.load_from_json(os.path.join(json_dir, f))
            parts = m['parts'].split(';')
            base = {'doc': file, 'revision': revision(file), 'category': m['categories'], 'parts': parts}
            cards, chars_original, chars_kept = doc_cards(doc, file, parts, chunker)
            for k, card in enumerate(cards):
                fc.write(json.dumps({**base, 'idx': k, **card, 'sha256': sha(card['text'])}, ensure_ascii=False) + '\n')
                seen.add(sha(card['text']))
            n_cards += len(cards)
            with open(os.path.join(pdf_dir, file), 'rb') as fp:
                pdf = fp.read()
            # [왜] 파일 이름은 source_url 끝에 있어 path를 따로 쓰지 않고, 공백 없는 JSON(separators)으로 크기를 줄인다
            fm.write(json.dumps({
                'doc_id': doc_key(file), 'title': re.sub(r'_[A-Z]\d{4}\.pdf$', '', file), 'revision': revision(file),
                'source_url': m['url'], 'sha256': hashlib.sha256(pdf).hexdigest(), 'bytes': len(pdf), 'pages': doc.num_pages(),
                'chunks': len(cards), 'chars_original': chars_original, 'chars_kept': chars_kept,
                'truncated': chars_kept < chars_original}, ensure_ascii=False, separators=(',', ':')) + '\n')
    summary = {'cards': n_cards, 'distinct_text': len(seen), 'chunker_version': CHUNKER_VERSION}
    with open(os.path.join(out_dir, 'summary.json'), 'w', encoding='utf-8') as fs:
        json.dump(summary, fs, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    main(*sys.argv[1:6])
