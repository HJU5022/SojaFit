"""데이터시트 PDF를 Docling으로 파싱하고, 표 숫자를 pdfplumber 글자와 두 방향으로 대조한다(오프라인 도구).

- 역할: 오프라인 CLI(`python -m backend.rag.parse`). 서버가 import하지 않는다.
  - run: PDF마다 Docling 결과를 <출력>/docling/<파일>.json으로 저장하고, 표 칸 숫자가 같은 쪽 pdfplumber 글자에
    있는지 센 결과(두 번째 증인)를 <출력>/witness/에, PDF별 쪽 수·초·표 수·일치 수를 <출력>/log.jsonl에 남긴다.
    결과가 이미 있는 PDF는 건너뛴다.
  - recall: 반대 방향. Docling 표 영역(bbox) 안의 원문 숫자가 Docling 표 칸에도 있는지 센다.
- 하지 않는 일: 청킹(chunk.py), PDF 수정. Docling이 아예 찾지 못한 표는 recall로도 셀 수 없다.
- 출처: docs/specs/rag-pipeline.md What 3·EC-02·EC-10, EVAL_REPORT.md 1장(11-01 GPU 전체 파싱의 설정)
- 의존성: uv 그룹 ingest(docling, pdfplumber). 서버 이미지에는 없다.
- 지원 범위: 맥·리눅스·도커(리눅스)에서 PDF마다 10분 시간 제한을 건다. Windows에는 SIGALRM이 없어 시간 제한 없이 돈다.

실행:
  uv run --group ingest python -m backend.rag.parse run <pdf 폴더> <출력 폴더>
  uv run --group ingest python -m backend.rag.parse recall <pdf 폴더> <docling json 폴더> <결과 json>
"""
import json
import os
import re
import signal
import sys
import time
from collections import Counter

TIMEOUT = 600  # [주의] PDF 하나가 10분을 넘으면 끊고 실패로 남긴다
HAS_ALARM = hasattr(signal, 'SIGALRM')  # [주의] Windows에는 SIGALRM이 없다
NUM = re.compile(r'(?<![\w.])[-+]?\d+(?:\.\d+)?(?![\w.])')  # 칸 안의 독립된 숫자


def make_converter():
    """OCR을 끄고 표 구조를 켠 Docling DocumentConverter를 만든다. 장치는 Docling이 고른다(CUDA·MPS·CPU)."""
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    opts = PdfPipelineOptions(do_ocr=False, do_table_structure=True,
                              accelerator_options=AcceleratorOptions(device=AcceleratorDevice.AUTO))
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})


def numbers(text):
    """글자 속 독립된 숫자를 {숫자 글자: 횟수}로 센다(μ와 µ는 같은 글자로 본다)."""
    return Counter(NUM.findall((text or '').replace('μ', 'µ')))


def witness(doc, pdf_path):
    """Docling 문서(doc)의 표 칸 숫자가 같은 쪽 pdfplumber 글자에 있는지 세어 {numbers, matched, unmatched_sample(최대 30개)}로 돌려준다."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        page_text = [re.sub(r'\s+', ' ', (p.extract_text() or '').replace('μ', 'µ')) for p in pdf.pages]
    total, hit, miss = 0, 0, []
    for t in doc.tables:
        page = t.prov[0].page_no if t.prov else None
        text = page_text[page - 1] if page and page <= len(page_text) else ' '.join(page_text)
        for c in t.data.table_cells:
            for n in NUM.findall(c.text):
                total += 1
                if re.search(r'(?<![\d.])' + re.escape(n) + r'(?![\d.])', text):
                    hit += 1
                elif len(miss) < 30:
                    miss.append({'page': page, 'cell': c.text[:80], 'number': n})
    return {'numbers': total, 'matched': hit, 'unmatched_sample': miss}


def run(pdf_dir, out_dir):
    """폴더의 PDF를 모두 파싱해 docling/·witness/·log.jsonl을 쓴다. 끊겨도 다시 돌리면 남은 것만 한다."""
    # [주의] PDF 하나의 실패(시간 초과 포함)는 log.jsonl의 error 칸에 남기고 다음 PDF로 넘어간다
    for d in ('docling', 'witness'):
        os.makedirs(os.path.join(out_dir, d), exist_ok=True)
    conv = make_converter()

    def _alarm(*_):
        """SIGALRM 처리기: 시간 제한이 지나면 TimeoutError를 올려 그 PDF를 실패로 남긴다."""
        raise TimeoutError(f'{TIMEOUT}초 초과')
    if HAS_ALARM:
        signal.signal(signal.SIGALRM, _alarm)
    else:
        print(f'[주의] 이 OS에는 SIGALRM이 없어 PDF별 {TIMEOUT}초 시간 제한 없이 돈다(맥·리눅스·도커 권장)', file=sys.stderr)
    alarm = signal.alarm if HAS_ALARM else (lambda _sec: None)
    log = open(os.path.join(out_dir, 'log.jsonl'), 'a', encoding='utf-8')  # 'a': 이어 붙인다. 다시 돌려도 앞 기록이 남는다
    for f in sorted(x for x in os.listdir(pdf_dir) if x.lower().endswith('.pdf')):
        out_json = os.path.join(out_dir, 'docling', f + '.json')
        if os.path.exists(out_json):
            continue
        row, t0 = {'pdf': f}, time.perf_counter()
        alarm(TIMEOUT)  # signal.alarm: TIMEOUT초 뒤 SIGALRM을 보낸다. 위 _alarm이 받아 TimeoutError로 바꾼다
        try:
            doc = conv.convert(os.path.join(pdf_dir, f)).document
            w = witness(doc, os.path.join(pdf_dir, f))  # [왜] 시간 제한(PDF마다 10분)이 대조까지 덮도록 여기서 푼다
            alarm(0)
            row.update(sec=round(time.perf_counter() - t0, 2), pages=doc.num_pages(), tables=len(doc.tables),
                       numbers=w['numbers'], matched=w['matched'])
            with open(os.path.join(out_dir, 'witness', f + '.json'), 'w', encoding='utf-8') as fw:
                json.dump(w, fw, ensure_ascii=False)
            # [왜] 결과 파일을 마지막에 써야 중간에 끊긴 PDF를 다음 실행에서 다시 한다
            with open(out_json, 'w', encoding='utf-8') as fd:
                json.dump(doc.export_to_dict(), fd, ensure_ascii=False)
        except Exception as e:
            alarm(0)
            row.update(sec=round(time.perf_counter() - t0, 2), error=f'{type(e).__name__}: {e}'[:200])
        log.write(json.dumps(row, ensure_ascii=False) + '\n')
        log.flush()
    log.close()


def table_box(bb, page_h, page_w):
    """Docling 표 bbox를 pdfplumber 좌표(왼쪽 위 원점)의 (x0, top, x1, bottom)로 바꾼다. 넓이가 없으면 None."""
    # [주의] Docling bbox는 보통 왼쪽 아래가 원점이고, pdfplumber는 왼쪽 위가 원점이다
    top, bottom = (page_h - bb['t'], page_h - bb['b']) if bb.get('coord_origin', 'BOTTOMLEFT') == 'BOTTOMLEFT' else (bb['t'], bb['b'])
    box = (max(0, bb['l']), max(0, top), min(page_w, bb['r']), min(page_h, bottom))
    return box if box[0] < box[2] and box[1] < box[3] else None


def recall_one(pdf_path, doc):
    """PDF 하나: (표 영역 원문 숫자 수, Docling 표에 없는 숫자 수, 빠진 예시)."""
    import pdfplumber
    total, missing, examples = 0, 0, []
    with pdfplumber.open(pdf_path) as pdf:
        for t in doc.get('tables', []):
            if not t.get('prov') or t['prov'][0]['page_no'] > len(pdf.pages):
                continue
            page_no, bb = t['prov'][0]['page_no'], t['prov'][0]['bbox']
            page = pdf.pages[page_no - 1]
            box = table_box(bb, doc['pages'][str(page_no)]['size']['height'], page.width)
            if box is None:
                continue
            src = numbers(' '.join(w['text'] for w in page.within_bbox(box).extract_words()))
            lost = src - numbers(' '.join(c.get('text', '') for c in t['data'].get('table_cells', [])))
            total, missing = total + sum(src.values()), missing + sum(lost.values())
            if lost and len(examples) < 10:
                examples.append({'page': page_no, 'lost': dict(lost.most_common(8))})
    return total, missing, examples


def recall(pdf_dir, json_dir, out_path):
    """폴더 전체의 반대 방향 대조 결과를 쓰고 요약을 돌려준다."""
    rows = []
    for f in sorted(x for x in os.listdir(json_dir) if x.endswith('.json')):
        with open(os.path.join(json_dir, f), encoding='utf-8') as fh:
            doc = json.load(fh)
        total, missing, ex = recall_one(os.path.join(pdf_dir, f[:-5]), doc)
        rows.append({'pdf': f[:-5], 'numbers_in_tables': total, 'missing_in_docling': missing, 'examples': ex})
    T, M = sum(r['numbers_in_tables'] for r in rows), sum(r['missing_in_docling'] for r in rows)
    summary = {'pdfs': len(rows), 'numbers_in_tables': T, 'missing_in_docling': M,
               'recall': round(1 - M / T, 4) if T else None, 'pdfs_with_missing': sum(r['missing_in_docling'] > 0 for r in rows)}
    with open(out_path, 'w', encoding='utf-8') as fo:
        json.dump({'summary': summary, 'rows': rows}, fo, ensure_ascii=False, indent=1)
    return summary


if __name__ == '__main__':
    cmd, *args = sys.argv[1:]
    if cmd == 'run':
        run(*args)
    elif cmd == 'recall':
        print(json.dumps(recall(*args), ensure_ascii=False))
    else:
        sys.exit(__doc__)
