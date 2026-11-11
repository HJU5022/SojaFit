"""제조사 표에서 인용 문장을 만들고 답변에 그대로 쓰였는지 검사한다."""
from hashlib import sha256
import re


def row_sentence(doc):
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
    condition = f" ({doc['conditions']})" if doc.get('conditions') else ''
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
