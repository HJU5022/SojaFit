"""Docling 파싱 결과를 검색 청크로 자르고 문서 목록(manifest)을 쓴다(오프라인 도구).

- 역할: 오프라인 CLI(`python -m backend.rag.pipeline.chunk`). 서버가 import하지 않는다.
  - PDF마다 청크: 품번 표지 + 표 밖 글 + 표 한 행 + 표와 섞여 빠진 글·표 캡션.
    표 청크는 합친 칸을 걸친 모든 자리에 채우고 앞에 [파일 · 쪽 · 표 제목] 이름표를 붙인다.
  - <출력>/chunks.jsonl(청크 하나 = 한 줄), <출력>/summary.json(청크 수, 서로 다른 본문 수), manifest.jsonl(문서 한 개 = 한 줄)
  - manifest에는 문서마다 다른 값만 쓴다. 모든 문서에 같은 값은 DOC_DEFAULTS에 두고 ingest.py가 읽을 때 채운다.
- 하지 않는 일: 임베딩·DB 적재(`ingest.py`), 파싱(`parse.py`). 단 `doc_key`·`DOC_DEFAULTS`·`CHUNKER_VERSION`은 `ingest.py`가 import해 쓴다.
- 출처: docs/specs/rag-pipeline.md What 4·AC-01~03·EC-03, EVAL_REPORT.md 1장 청킹 비교(개선 2)
- 의존성: 표 청크 함수는 표준 라이브러리만 쓴다. 실행(main)에는 uv 그룹 ingest(docling)가 필요하다.

실행: uv run --group ingest python -m backend.rag.pipeline.chunk <docling json 폴더> <목록 csv> <pdf 폴더> <출력 폴더> <manifest.jsonl>
"""
import csv
import hashlib
import json
import os
import re
import sys
import unicodedata

CHUNKER_VERSION = 'tsc-cards-waveform-notes-2026-11-06'
PARSER = 'docling 2.145.0 (OCR off)'
USAGE = 'See data/corpus/CORPUS.md; informational/non-commercial, unmodified PDF, notices retained and source attributed.'
# [왜] 1,360줄에 같은 값을 되풀이하면 manifest가 1MB를 넘어 Checkpoint 대시보드가 읽지 못한다(512,000바이트 아래로 둔다).
# [주의] 이 값과 다른 문서(다른 제조사, 인젝션 시험 문서)는 manifest 줄에 그 키를 적으면 줄의 값이 앞선다.
DOC_DEFAULTS = {'manufacturer': 'Taiwan Semiconductor', 'collected_at': '2026-11-01', 'parser': PARSER,
                'status': 'parsed_chunked', 'purpose': 'corpus', 'usage_conditions': USAGE}


def sha(text):
    """글자의 sha256 16진 문자열(청크 본문 해시, chunk_sha256)."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def doc_key(file):
    """'1N4148 SERIES_K2301.pdf' → 'tsc-1n4148-series_k2301' (manifest doc_id, DB document_key)."""
    return 'tsc-' + file[:-4].lower().replace(' ', '-')


def revision(file):
    """파일 이름 끝의 개정판 코드(예: '..._H2104.pdf' → 'H2104')."""
    m = re.search(r'_([A-Z]\d{4})\.pdf$', file)
    return m.group(1) if m else None


def table_cards(file, page, n_rows, n_cols, cells):
    """표 하나를 데이터 행마다 청크 하나으로 만든다(AC-01·AC-02)."""
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


_NUMBER = r'\d+(?:\.\d+)?(?:e[+-]?\d+)?'
_PULSE = re.compile(rf'(?:pulse\s*width|pw|tp)\s*[:=<>≤≥≦≧]*\s*{_NUMBER}\s*(?:ns|μs|us|ms|s)', re.I)
_DUTY = re.compile(rf'(?:{_NUMBER}\s*%\s*duty\s*cycle|duty\s*cycle\s*[:=<>≤≥≦≧]*\s*{_NUMBER}\s*%)', re.I)
_FIGURE = re.compile(r'fig(?:ure)?\.?\s*\d+[a-z]?\b[\s.:–-]*\S+.*', re.I)


def _leading_s_figure(text):
    return text.startswith('sFig.') and _FIGURE.fullmatch(text[1:]) is not None


def _thermal_bias_conditions(picture, title, resolve, box, page, pb):
    """검수한 문구만 선택하고 동일 그림의 인접한 줄을 원문 그대로 묶는다."""
    thermal = 'derating' in title.casefold()
    bias = bool(re.search(r'capacitance|typical reverse characteristics', title, re.I))
    if not (thermal or bias):
        return []
    dim = rf'{_NUMBER}\s*mm\s*x\s*{_NUMBER}\s*mm'
    inch = rf'{_NUMBER}"\s*x\s*{_NUMBER}"'
    patterns = {
        'mounting': rf'(?:heat[- ]sink\s+{dim}\s+cu pad test board|mounted on PCB with\s+cu-pad size\s+{dim}|with(?:out)? heat sink(?:\s+{dim}\s+cu-pad)?|heat-sink\s+mounting\s+{inch}\s*x\s*{_NUMBER}"\s+al-plate|P\.C\.B\.\s+mounting\s+{inch}\s+copper pads)',
        'bias': r'(?:v\s*r\s*=\s*0(?:\s*v)?|measured\s+at\s+(?:devices\s+)?(?:zero\s+bias|stand-off\s+voltage\s*[, ]*v\s*wm|stand-off\s+voltage\s*\(v\)|v\s*wm))',
        'frequency': rf'f\s*=\s*{_NUMBER}\s*(?:Hz|kHz|MHz)',
        'signal': rf'v\s*sig\s*=\s*{_NUMBER}\s*(?:mV|V)\s*p\s*-\s*p',
    }
    def kind_of(text):
        return ('mounting' if thermal and re.match(r'(?:heat[- ]sink|with(?:out)? heat sink|mounted on PCB|P\.C\.B\.)', text, re.I)
                else 'frequency' if bias and re.match(r'f\s*=', text, re.I)
                else 'signal' if bias and re.match(r'v\s*sig\s*=', text, re.I)
                else 'bias' if bias and re.match(r'(?:measured\s+at|v\s*r\s*=)', text, re.I) else None)
    items = {}
    for ref in picture.children:
        item = resolve(ref)
        raw = getattr(item, 'text', '')
        text = unicodedata.normalize('NFKC', raw).strip()
        b = box(item, page)
        if (b is None or item.parent is None or item.parent.cref != picture.self_ref
                or not (pb.l <= b.l < b.r <= pb.r and pb.b <= b.b < b.t <= pb.t)):
            if kind_of(text):
                return []
            continue
        key = (text.casefold(), *(round(v, 1) for v in (b.l, b.t, b.r, b.b)))
        if key not in items:
            items[key] = {'text': raw, 'normalized': text, 'box': b, 'source_refs': []}
        items[key]['source_refs'].append(item.self_ref)
    items = list(items.values())
    conditions, used = [], set()
    for first in items:
        if any(ref in used for ref in first['source_refs']):
            continue
        text = first['normalized']
        kind = kind_of(text)
        if kind is None:
            continue
        path, matches, branched = [first], [], False
        for _ in range(4):
            combined = ' '.join(it['normalized'] for it in path)
            if re.fullmatch(patterns[kind], combined, re.I):
                matches.append(list(path))
            if kind in ['frequency', 'signal']:
                break
            b = path[-1]['box']
            continuation = rf'(?:mounting|{dim}(?:\s+cu-pad)?|cu pad test board|cu-pad size\s+{dim}|{inch}(?:\s*x\s*{_NUMBER}")?|al-plate|copper pads|stand-off|zero bias|voltage\s*[, ]*v\s*wm|voltage\s*\(v\)|stand-off voltage\s*[, ]*v\s*wm)'
            following = [it for it in items if it not in path and re.fullmatch(continuation, it['normalized'], re.I)
                         and abs(it['box'].l - b.l) <= 3
                         and -0.2 * min(b.t - b.b, it['box'].t - it['box'].b) <= b.b - it['box'].t
                         <= 0.8 * max(b.t - b.b, it['box'].t - it['box'].b)]
            if len(following) != 1:
                branched = len(following) > 1
                break
            path.append(following[0])
        if not matches or branched:
            return []  # 대안 하나가 빠진 상태에서 나머지를 공통 조건으로 오인하지 않는다.
        chosen = matches[-1]
        refs = list(dict.fromkeys(r for it in chosen for r in it['source_refs']))
        used.update(refs)
        conditions.append({'source_ref': refs[0], 'source_refs': refs, 'type': kind,
                           'text': '\n'.join(it['text'] for it in chosen)})
    for kind in ['frequency', 'signal']:
        values = {''.join(c['text'].casefold().split()) for c in conditions if c['type'] == kind}
        if len(values) > 1:
            return []  # shortcut: 주파수/진폭 다중 값은 곡선 대응을 검증한 뒤 확장한다.
    for c in conditions:
        c['role'] = ('curve_legend' if c['type'] in ['mounting', 'bias']
                     and len({''.join(x['text'].casefold().split()) for x in conditions if x['type'] == c['type']}) > 1
                     else 'common_measurement')
    return conditions


def _graph_note_cards(doc, file, resolve, box):
    """완결된 정의/주석을 교정 없이 보존하고 주석 위치에서 제목을 확인한다."""
    definitions = (rf'pulse\s+width\s*\(\s*t\s*[dp]\s*\)\s+is defined\s+as\s+(?:the\s+)?point\s+where\s+the\s+peak\s+current\s+decays\s+to\s+50\s*%\s+of\s+i\s*p\s*pm',
                   rf'pulse\s+width\s*\(\s*tp\s*\)\s+is defined\s+as that point where the\s+peak current decay\s*=\s*{_NUMBER}\s*us')
    rules = {
        'waveform_definition': ('pulse waveform', '|'.join(definitions), '[파형 정의 — 원문]'),
        'graph_applicability_note': ('typical thermal response', rf'note below\s+{_NUMBER}\s+second,\s+thermal response\s+curve is applicable to\s+any lead length\(l\)', '[그래프 적용 주석 — 원문]'),
        'graph_interpretation_note': ('effect of zener current', r'note\s*:\s*below 3 voltage above a\s+volts changes in zener current\s+not affect temperature\s+coefficients', '[그래프 해석 주석 — 원문 그대로, 교정하지 않음]'),
    }
    continuation = r'(?:as the point where the peak|current decays to 50\s*% of i\s*p\s*pm|is defined as the point|where the peak current|decays to 50\s*% of i\s*p\s*pm|as that point where the|peak current decay\s*=\s*' + _NUMBER + r'\s*us|thermal response|curve is applicable to|any lead length\(l\)|volts changes in zener current|not affect temperature(?: coefficients)?|coefficients)'
    auxiliary = rf'(?:(?:rise time\s+)?t\s*r\s*=\s*{_NUMBER}\s*(?:μs|us|ms|ns)(?:\s+to\s+100%(?:\s+of\s+i\s*p\s*pm)?)?|{_NUMBER}/{_NUMBER}\s*(?:μs|us),?\s+waveform|half value[^\n]*/\s*2(?:\s*@\s*{_NUMBER}\s*us)?|i\s*rsm\s*@\s*{_NUMBER}\s*us|peak value\s+i\s*p\s*pm|as defined by R\.E\.A\.)'
    cards, diagnostics = [], []
    for picture in doc.pictures:
        if len(picture.prov) != 1:
            continue
        page = picture.prov[0].page_no
        pb = box(picture, page)
        if pb is None:
            continue
        items = []
        for ref in picture.children:
            item = resolve(ref)
            if not getattr(item, 'prov', None):
                continue
            b = box(item, page)
            if (b is not None and item.parent is not None and item.parent.cref == picture.self_ref
                    and pb.l <= b.l < b.r <= pb.r and pb.b <= b.b < b.t <= pb.t):
                items.append((item, b, unicodedata.normalize('NFKC', getattr(item, 'text', '')).strip()))
        for first in items:
            prefix = first[2].casefold()
            role = ('waveform_definition' if re.match(r'pulse\s+width\s*\(\s*t\s*[dp]\s*\)', prefix)
                    else 'graph_applicability_note' if prefix.startswith('note below')
                    else 'graph_interpretation_note' if prefix.startswith('note:below') else None)
            if role is None:
                continue
            family, pattern, heading = rules[role]
            info = {'source_kind': 'graph_note', 'figure_ref': picture.self_ref, 'page': page,
                    'condition_role': role, 'conditions': [], 'status': 'incomplete_note'}
            diagnostics.append(info)
            path, chosen, branched = [first], None, False
            for _ in range(4):
                if re.fullmatch(pattern, ' '.join(it[2] for it in path), re.I):
                    chosen = list(path)
                    break
                b = path[-1][1]
                following = [it for it in items if it not in path and re.fullmatch(continuation, it[2], re.I)
                             and abs(it[1].l - b.l) <= 3
                             and -0.2 * min(b.t - b.b, it[1].t - it[1].b) <= b.b - it[1].t
                             <= 0.8 * max(b.t - b.b, it[1].t - it[1].b)]
                if len(following) != 1:
                    branched = len(following) > 1
                    break
                path.append(following[0])
            if chosen is None or branched:
                continue
            titles = []
            for title in doc.texts:
                tb = box(title, page)
                if (tb is not None and _FIGURE.fullmatch(title.text.strip()) and family in title.text.casefold()
                        and min(first[1].r, tb.r) > max(first[1].l, tb.l)
                        and -1.5 * (tb.t - tb.b) <= tb.b - pb.t <= max(6 * (tb.t - tb.b), 0.25 * (pb.t - pb.b))
                        and tb.b >= first[1].t):
                    titles.append(title)
            if len(titles) != 1:
                info['status'] = 'no_unique_note_title'
                continue
            title = titles[0]
            refs = [it[0].self_ref for it in chosen]
            text = '\n'.join(it[0].text for it in chosen)
            info['conditions'].append({'source_ref': refs[0], 'source_refs': refs, 'type': role, 'role': role, 'text': text})
            sections = [heading + '\n' + text]
            if role == 'waveform_definition':
                annotations = [it for it in items if it not in chosen and re.fullmatch(auxiliary, it[2], re.I)]
                if annotations:
                    sections.append('[파형 보조 표기 — 원문]\n' + '\n'.join(it[0].text for it in annotations))
                    for it in annotations:
                        info['conditions'].append({'source_ref': it[0].self_ref, 'source_refs': [it[0].self_ref],
                                                   'type': 'waveform_annotation', 'role': 'waveform_annotation', 'text': it[0].text})
            text = f'[{file} · {page}쪽 · {title.text}]\n' + '\n'.join(sections)
            info.update(status='accepted', title=title.text, title_ref=title.self_ref, title_method='note_spatial_title', card_text=text)
            cards.append({'kind': 'text', 'page': page, 'table': None, 'row': None, 'text': text})
    return cards, diagnostics


def graph_condition_cards(doc, file):
    """명확히 연결된 그래프 제목·펄스/듀티 조건 청크와 그림별 판별 기록을 반환한다."""
    cards, diagnostics = [], []
    if not doc.pictures:
        return cards, diagnostics
    global_titles = [t for t in doc.texts if _FIGURE.fullmatch(t.text.strip())]
    extended_titles = [t for t in doc.texts if _leading_s_figure(t.text.strip())]
    pending, extensions, primary_titles = [], [], set()
    contexts, title_owners = [], {}
    def resolve(ref):
        try:
            return ref.resolve(doc)
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(f'그래프 원문 참조를 찾을 수 없음: {ref.cref}') from exc
    def box(item, page):
        if len(item.prov) == 1 and item.prov[0].page_no == page:
            b = item.prov[0].bbox
            if b.coord_origin == 'BOTTOMLEFT' and b.l < b.r and b.b < b.t:
                return b
        return None
    def near_above(tb, pb):
        return (tb is not None and pb is not None
                and 0 <= tb.b - pb.t <= max(6 * (tb.t - tb.b), 0.25 * (pb.t - pb.b))
                and min(pb.r, tb.r) > max(pb.l, tb.l))
    for picture in doc.pictures:
        info = {'figure_ref': picture.self_ref, 'status': 'no_unique_figure_title', 'conditions': []}
        diagnostics.append(info)
        caption_items = [resolve(r) for r in picture.captions]
        titles = [t for t in caption_items if _FIGURE.fullmatch(getattr(t, 'text', '').strip())]
        if not titles:
            titles = [t for t in caption_items if _leading_s_figure(getattr(t, 'text', '').strip())]
        if len(titles) > 1 or len(picture.prov) != 1:
            continue
        page = picture.prov[0].page_no
        title = titles[0] if titles else None
        pb, tb = box(picture, page), box(title, page) if title is not None else None
        child_refs = [r.cref for r in picture.children]
        if pb is None:
            info['status'] = 'invalid_title_provenance'
            continue
        method = 'metadata'
        valid_link = (title is not None and title.parent is not None
                      and title.parent.cref == picture.self_ref and title.self_ref in child_refs)
        if not valid_link or not near_above(tb, pb):
            info['original_status'] = 'no_unique_figure_title' if title is None else 'invalid_title_provenance' if not valid_link else 'title_outside_position'
            info['original_title_refs'] = [r.cref for r in picture.captions]
            candidates = []
            for t in global_titles:
                b = box(t, page)
                if near_above(b, pb) and pb.l <= (b.l + b.r) / 2 <= pb.r:
                    candidates.append(t)
            if not candidates:
                for t in extended_titles:
                    b = box(t, page)
                    if near_above(b, pb) and pb.l <= (b.l + b.r) / 2 <= pb.r:
                        candidates.append(t)
            info['spatial_candidate_refs'] = [t.self_ref for t in candidates]
            if len(candidates) != 1:
                info['status'] = 'no_spatial_title' if not candidates else 'ambiguous_spatial_title'
                continue
            title, method = candidates[0], 'spatial_fallback'
        info.update(title=title.text, title_ref=title.self_ref, page=page, title_method=method)
        info['title_recognition'] = 'leading_s' if _leading_s_figure(title.text.strip()) else 'numbered'
        title_owners.setdefault(title.self_ref, set()).add(picture.self_ref)
        context = _thermal_bias_conditions(picture, title.text, resolve, box, page, pb)
        if context:
            context_info = {**info, 'source_kind': 'thermal_bias_context', 'conditions': context}
            contexts.append(context_info)
        conditions, kinds, invalid = [], {}, False
        info['unselected_refs'] = []
        for ref in picture.children:
            item = resolve(ref)
            text = getattr(item, 'text', '')
            normalized = unicodedata.normalize('NFKC', text).strip()
            kind = 'pulse_width' if _PULSE.fullmatch(normalized) else 'duty_cycle' if _DUTY.fullmatch(normalized) else None
            if kind is None:
                if item.self_ref != title.self_ref:
                    info['unselected_refs'].append(item.self_ref)
                continue
            b = box(item, page)
            if (b is None or item.parent is None or item.parent.cref != picture.self_ref
                    or not (pb.l <= b.l < b.r <= pb.r and pb.b <= b.b < b.t <= pb.t)):
                invalid = True
                info['status'] = 'condition_outside_provenance'
                break
            canonical = ''.join(normalized.casefold().split())
            key = (kind, canonical)
            if key not in kinds:
                entry = {'source_ref': item.self_ref, 'source_refs': [item.self_ref], 'type': kind, 'text': text}
                conditions.append(entry)
                kinds[key] = entry
            elif item.self_ref not in kinds[key]['source_refs']:
                kinds[key]['source_refs'].append(item.self_ref)
        info['conditions'] = conditions
        if invalid:
            continue
        if not conditions:
            info['status'] = 'no_supported_numeric_condition'
            continue
        types = {c['type'] for c in conditions}
        multiple = any(sum(c['type'] == kind for c in conditions) > 1 for kind in types)
        role = 'common_measurement'
        if multiple:
            family_title = title.text.strip()
            if info['title_recognition'] == 'leading_s':
                family_title = family_title[1:]
            reviewed = ((re.fullmatch(r'fig(?:ure)?\.?\s*\d+\s+Maximum Surge Power', family_title, re.I) and types == {'duty_cycle'})
                        or (re.fullmatch(r'fig(?:ure)?\.?\s*\d+\s+Clamping Voltage Curve', family_title, re.I)
                            and types == {'pulse_width'} and all(re.match(r'tp\b', c['text'].strip(), re.I) for c in conditions)))
            if not reviewed:
                info['status'] = 'ambiguous_condition_values'
                continue
            role = 'curve_legend'
        info['condition_role'] = role
        heading = '[그래프 측정 조건]' if role == 'common_measurement' else '[곡선별 범례 — 서로 다른 곡선의 대안 값, 공통 측정 조건이 아님]'
        text = f'[{file} · {page}쪽 · {title.text}]\n{heading}\n' + '\n'.join(c['text'] for c in conditions)
        info.update(status='accepted', card_text=text)
        card = {'kind': 'text', 'page': page, 'table': None, 'row': None, 'text': text}
        expanded = role == 'curve_legend' or info['title_recognition'] == 'leading_s'
        if method == 'metadata':
            (extensions if expanded else cards).append(card)
            primary_titles.add(title.self_ref)
        else:
            pending.append((card, info))
    claims = {}
    for card, info in pending:
        claims.setdefault(info['title_ref'], set()).add(info['figure_ref'])
    # 유효했던 그래프 순서를 보존하고, 보완 제목을 여러 그림이 공유하면 추정하지 않는다.
    for card, info in pending:
        if info['title_ref'] in primary_titles or len(claims[info['title_ref']]) != 1:
            info['status'] = 'spatial_title_shared'
        else:
            (extensions if info['condition_role'] == 'curve_legend' or info['title_recognition'] == 'leading_s' else cards).append(card)
    cards.extend(extensions)
    for info in contexts:
        diagnostics.append(info)
        if len(title_owners[info['title_ref']]) != 1:
            info['status'] = 'spatial_title_shared'
            continue
        sections = []
        for role, heading in [('common_measurement', '[그래프 공통 측정 조건]'),
                              ('curve_legend', '[곡선별 범례 — 서로 다른 곡선의 대안 값, 공통 측정 조건이 아님]')]:
            values = list(dict.fromkeys(c['text'] for c in info['conditions'] if c['role'] == role))
            if values:
                sections.append(heading + '\n' + '\n---\n'.join(values))
        text = f"[{file} · {info['page']}쪽 · {info['title']}]\n" + '\n'.join(sections)
        info.update(status='accepted', condition_role='thermal_bias_context', card_text=text)
        cards.append({'kind': 'text', 'page': info['page'], 'table': None, 'row': None, 'text': text})
    note_cards, note_diagnostics = _graph_note_cards(doc, file, resolve, box)
    cards.extend(note_cards)
    diagnostics.extend(note_diagnostics)
    return cards, diagnostics


def doc_cards(doc, file, parts, chunker):
    """Docling 문서 하나를 (청크 목록: 표지·표 밖 글·표 행 순서, 원문 글자 수, 청크에 들어간 원문 글자 수)로 바꾼다."""
    from docling_core.types.doc import TableItem, TextItem
    cards = [{'kind': 'cover', 'page': None, 'table': None, 'row': None,
              'text': f'[{file}] 이 데이터시트의 품번: {", ".join(parts)}'}]
    kept_refs, headings, skipped_refs = set(), set(), []
    for c in chunker.chunk(doc):
        if any(isinstance(it, TableItem) for it in c.meta.doc_items):  # 표는 아래에서 행 단위로 따로 만든다
            skipped_refs.extend(it.self_ref for it in c.meta.doc_items if not isinstance(it, TableItem))
            continue
        kept_refs.update(it.self_ref for it in c.meta.doc_items)
        headings.update(c.meta.headings or [])  # [왜] 소제목은 doc_items가 아니라 contextualize가 청크 앞에 붙인다
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
    # 원문 글자 수 = 본문(머리글·바닥글 제외) 글 조각 + 표 칸. 청크에 들어간 글자 수 = 글 청크에 든 조각 + 청크를 만든 표의 칸
    # 이름표·표지·반복되는 열 이름은 원문이 아니라 세지 않는다.
    body = [it for it, _ in doc.iterate_items()]
    by_ref = {it.self_ref: it for it in body}
    caption_refs = [ref.cref for table in doc.tables for ref in table.captions]
    for ref in dict.fromkeys(skipped_refs + caption_refs):
        if ref not in by_ref:
            raise ValueError(f'청크 원문 참조를 찾을 수 없음: {ref}')
        it = by_ref[ref]
        if not isinstance(it, TextItem):
            continue
        # 캡션은 doc_items에 있어도 본문에서 생략될 수 있으므로 실제 출력으로 확인한다.
        retained = any(it.text in card['text'] for card in cards) if ref in caption_refs else ref in kept_refs
        if not retained:
            cards.append({'kind': 'text', 'page': it.prov[0].page_no if it.prov else None,
                          'table': None, 'row': None, 'text': it.text})
            kept_refs.add(ref)
    texts = [it for it in body if isinstance(it, TextItem)]
    tables = [it for it in body if isinstance(it, TableItem)]
    table_chars = {t.self_ref: sum(len(c.text) for c in t.data.table_cells) for t in tables}
    original = sum(len(it.text) for it in texts) + sum(table_chars.values())
    kept = sum(len(it.text) for it in texts if it.self_ref in kept_refs or it.text in headings) + \
        sum(table_chars.get(r, 0) for r in kept_tables)
    graph_cards, _ = graph_condition_cards(doc, file)
    existing_texts = {card['text'] for card in cards}
    for card in graph_cards:
        if card['text'] not in existing_texts:
            cards.append(card)
            existing_texts.add(card['text'])
    # original/kept는 기존 본문·표 범위의 수치이며 그림 내부 조건은 진단에서 따로 센다.
    return cards, original, kept


def main(json_dir, list_csv, pdf_dir, out_dir, manifest_path):
    """Docling json 폴더를 청크(chunks.jsonl)와 문서 목록(manifest.jsonl)으로 바꾸고 summary.json을 쓴다."""
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
