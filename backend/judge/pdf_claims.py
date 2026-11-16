"""제조사 표에서 인용 문장을 만들고 답변에 그대로 쓰였는지 검사한다."""
from hashlib import sha256
import math
import re


def _recovery_values(doc, reading):
    if not isinstance(reading, dict) or not all(reading.get(k) is True for k in
            ('readable', 'start_on_zero_crossing', 'end_on_recovery')) or reading.get('unit') != 'A':
        return None
    values = {}
    for key in ('IF', 'IR', 'Irr'):
        match = re.search(r'\b' + key + r'\s*=\s*(\d+(?:\.\d+)?)\s*A\b', doc.get('conditions', ''))
        if not match:
            return None
        values[key] = float(match[1])
    expected = {'forward_current': values['IF'], 'reverse_peak': -values['IR'],
                'recovery_end': -values['Irr'], 'arrow_start': 0, 'arrow_end': -values['Irr']}
    for key, number in expected.items():
        observed = reading.get(key)
        if not isinstance(observed, (int, float)) or not math.isfinite(observed) or not math.isclose(observed, number, abs_tol=1e-9):
            return None
    return values


def recovery_figure_doc(parent, reading, chunk_id):
    """Accept an observed recovery diagram only when its currents match the same PDF table."""
    figure = parent.get('figure') or {}
    if (not _recovery_values(parent, reading) or not re.search(r'reverse recovery', parent.get('row', ''), re.I)
            or not re.search(r'reverse recovery.*(?:test circuit|characteristic)', figure.get('caption', ''), re.I)
            or not isinstance(figure.get('page'), int) or figure['page'] <= 0
            or not parent.get('source_sha256') or parent.get('evidence_grade') != 2):
        return None
    doc = {k: parent[k] for k in ('file', 'source_url', 'source_sha256', 'source_type',
                               'evidence_grade', 'retrieved_at', 'doc_parts', 'conditions') if k in parent}
    doc.update(chunk_id=chunk_id, page=figure['page'], table=figure['caption'], row='Reverse recovery waveform',
               figure_reading=reading, figure_reading_method='haiku-vision/table-current-crosscheck')
    doc['content'] = row_sentence(doc)
    return doc


def row_sentence(doc):
    if reading := doc.get('figure_reading'):
        values = _recovery_values(doc, reading)
        if not values or len(doc.get('doc_parts') or []) != 1:
            return ''
        forward, peak, end = (f'{values[key]:g}' for key in ('IF', 'IR', 'Irr'))
        return (f"{doc['doc_parts'][0]}의 {doc['table']} 파형은 +{forward} A에서 0 A를 지나 "
                f"−{peak} A에 도달한 뒤 −{end} A로 회복하며, trr은 0 A 하강 교차점부터 "
                f"회복 중 −{end} A 끝점까지 표시된 구간으로, 이는 해당 시험의 측정 기준이며 "
                f"실제 코일의 실측값이나 교체 적합성을 보장하지 않습니다 [{doc['chunk_id']}].")
    parts, cells, unit = doc.get('doc_parts'), doc.get('cells'), doc.get('unit')
    if not parts or len(parts) != 1 or not cells or not unit or not doc.get('row'):
        return ''
    part = parts[0]
    values = []
    for column, value in cells:
        if column == part:
            values.append(f'{value} {unit}')
        elif column in ('MIN', 'TYP', 'MAX', 'VALUE'):
            values.append(f'{column} {value} {unit}')
        else:
            return ''
    conditions = doc.get('conditions', '')
    if re.search(r'reverse recovery', doc.get('row', ''), re.I):
        ambient = re.search(r'TA\s*=\s*[+−-]?\d+(?:\.\d+)?\s*°C', doc.get('table', ''))
        if ambient and ambient[0] not in conditions:
            conditions = '; '.join(filter(None, (conditions, ambient[0])))
    condition = f" ({conditions})" if conditions else ''
    if (doc.get('requested_symbol') == 'VRRM'
            and re.sub(r'[^A-Z]', '', str(doc.get('symbol', '')).upper()) == 'VR'
            and doc['row'] == 'Diode reverse voltage'):
        sentence = (f"{part}의 공식 표 항목은 VR(역전압), {doc['row']}{condition}이며 "
                f"값은 {', '.join(values)}이며, 요청하신 VRRM(반복 피크 역전압)은 "
                f"이 행으로 확인되지 않으므로 이 VR 값을 VRRM으로 대신 답하거나 "
                f"대체 판정에 사용하지 않습니다 [{doc['chunk_id']}].")
        return sentence.replace('입니다. 요청하신', '입니다; 요청하신').replace('않습니다. 이 VR', '않으며, 이 VR')
    return f"{part}의 {doc['row']}{condition} 값은 {', '.join(values)}입니다 [{doc['chunk_id']}]."


def sentence_digest(sentence):
    return sha256(sentence.encode('utf-8')).hexdigest()


def check_pdf_lines(answer, docs, *, expand=False):
    """독립된 줄의 W 인용을 검사한다. 문서 노드에서만 번호를 원문 셀로 펼친다."""
    rows = {doc['chunk_id']: doc for doc in docs if doc.get('source_type') == 'external_web'}
    lines = []
    for line in answer.splitlines():
        ids = set(re.findall(r'\bW[1-9][0-9]*\b', ' '.join(re.findall(r'\[([^\]]+)\]', line))))
        if ids:
            if len(ids) != 1 or (cid := next(iter(ids))) not in rows:
                return None
            row = rows[cid]
            if expand:
                sentence = row_sentence(row)
                if not sentence or line.strip() not in (f'[{cid}]', f'[{cid}].', sentence):
                    return None
                line = sentence
            elif sentence_digest(line.strip()) != row.get('sentence_sha256'):
                return None
        lines.append(line)
    return '\n'.join(lines)


def bind_run_citations(reports):
    """각 보고의 검색 번호를 체크포인트의 회차·작업 순서에 따라 실행 번호로 바꾼다."""
    numbers = {}
    next_number = 1
    for report in sorted(reports, key=lambda r: (r.round, r.task)):
        external = [d for d in report.docs if d.get('source_type') == 'external_web']
        if not external:
            continue
        local = {d['chunk_id']: d for d in external}
        if len(local) != len(external) or check_pdf_lines(report.answer, external) is None:
            return False
        claims = {}
        for line in report.answer.splitlines():
            match = re.search(r' \[(W[1-9][0-9]*)\]\.$', line)
            if match and match[1] in local:
                claims[match[1]] = line[:match.start()]
        if set(claims) != {cid for cid in report.evidence_ids if cid.startswith('W')}:
            return False
        first_report = not numbers
        bound = {}
        for label in sorted(claims, key=lambda cid: int(cid[1:])):
            doc, claim = local[label], claims[label]
            key = (doc['source_url'], doc['page'], doc['table'], doc['row'], claim)
            if key not in numbers:
                number = int(label[1:]) if first_report else next_number
                numbers[key] = f'W{number}'
                next_number = max(next_number, number + 1)
            cid = numbers[key]
            bound[label] = {**doc, 'chunk_id': cid, 'sentence_sha256': sentence_digest(f'{claim} [{cid}].')}
        # 한 번에 치환해야 같은 보고의 W1→W2, W2→W3가 서로 덮어쓰지 않는다.
        report.answer = re.sub(r'\[(W[1-9][0-9]*)\](?=\.$)', lambda m: f"[{bound[m[1]]['chunk_id']}]",
                               report.answer, flags=re.MULTILINE)
        report.evidence_ids = [bound[c]['chunk_id'] if c in bound else c for c in report.evidence_ids]
        report.docs = [d for d in report.docs if d.get('source_type') != 'external_web'] + list(bound.values())
    return True
