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
        ids = set(re.findall(r'\bW[1-3]\b', ' '.join(re.findall(r'\[([^\]]+)\]', line))))
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
