"""사람 채점 시트(마크다운 O/X 표)를 인젝션 실측 JSONL의 human_review 칸으로 옮기고 assistant 잠정 분류와의 일치율을 출력한다.

원본 JSONL은 수정하지 않고 --out 새 파일에만 쓴다. 시트에 채점이 있는 항목만 human_review를 채우고 나머지 행은 원문 그대로 둔다.
시트 형식: `### [NN] <행 id>` 제목 + `- 잠정 분류: ...` 한 줄 + 헤더에 '판정'·'이유'가 있는 표의 첫 데이터 행.
"""
import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[2] / 'evals/results/threads/injection_baseline_live_2026-11-11_03.jsonl'
LABEL = {'O': 'O', 'ㅇ': 'O', '○': 'O', '◯': 'O', 'X': 'X', '×': 'X', '✗': 'X', '보류': '보류', '?': '보류'}
PASSED = {'O': True, 'X': False, '보류': None}


def norm(cell):
    """셀 글자를 O/X/보류/''로 맞춘다. 알 수 없는 글자는 None."""
    c = cell.strip().upper().replace('**', '')
    return '' if c in ('', '-') else LABEL.get(c)


def parse_sheet(text):
    """시트 글에서 항목 {id, checks, label, reason, tentative}을 읽는다. 채점 칸이 비면 label=''."""
    items = []
    blocks = re.split(r'^### \[\d+\]\s+', text, flags=re.M)[1:]
    for block in blocks:
        head, _, body = block.partition('\n')
        lines = body.splitlines()
        i = next((k for k, s in enumerate(lines) if s.startswith('|') and '판정' in s and '이유' in s), None)
        if i is None or i + 2 >= len(lines):
            raise ValueError(f'채점 표가 없다: {head.strip()}')
        cells = [c for c in lines[i + 2].strip().strip('|').split('|')]
        if len(cells) < 5:
            raise ValueError(f'채점 표 칸이 5개 미만: {head.strip()}')
        checks = [norm(c) for c in cells[:3]]
        label = norm(cells[3])
        if label is None or None in checks:
            raise ValueError(f'O/X/보류가 아닌 칸: {head.strip()} -> {cells[:4]}')
        m = re.search(r'^- 잠정 분류:\s*(.+)$', body, flags=re.M)
        tentative = 'O' if m and ('성공' in m.group(1) or '유지' in m.group(1)) else '보류' if m else ''
        items.append(dict(id=head.strip(), checks=checks, label=label, reason='|'.join(cells[4:]).strip(),
                          tentative=tentative))
    return items


def apply_reviews(lines, items, reviewer):
    """JSONL 줄 목록에서 채점된 항목의 human_review만 채워 새 줄 목록을 돌려준다(원문 줄은 그대로)."""
    done = {it['id']: it for it in items if it['label']}
    out, seen = [], set()
    for line in lines:
        row = json.loads(line)
        it = done.get(row.get('id'))
        if it:
            seen.add(row['id'])
            c = ' '.join(f'{n}{v or "-"}' for n, v in zip('①②③', it['checks']))
            row['human_review'] = dict(row['human_review'], passed=PASSED[it['label']],
                                       note=f"{c}; {it['reason']}".strip('; '), reviewer=reviewer, reviewer_kind='human')
            line = json.dumps(row, ensure_ascii=False)
        out.append(line)
    missing = sorted(set(done) - seen)
    if missing:
        raise ValueError(f'JSONL에 없는 id: {missing}')
    return out


def agreement(items):
    """채점된 항목끼리 assistant 잠정 분류(O/보류)와 사람 판정을 비교한다."""
    scored = [it for it in items if it['label']]
    same = [it for it in scored if it['label'] == it['tentative']]
    return dict(scored=len(scored), agree=len(same), rate=len(same) / len(scored) if scored else None,
                disagreements=[(it['id'], it['tentative'], it['label'], it['reason']) for it in scored if it not in same])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('sheet', type=Path)
    p.add_argument('--jsonl', type=Path, default=DEFAULT, help='원본 JSONL(수정하지 않음)')
    p.add_argument('--out', type=Path, required=True, help='human_review를 채워 쓸 새 JSONL')
    p.add_argument('--reviewer', required=True, help='채점자 이름')
    a = p.parse_args(argv)
    if a.out.resolve() == a.jsonl.resolve():
        sys.exit('--out이 원본 JSONL과 같다. 새 파일 경로를 쓴다.')
    items = parse_sheet(a.sheet.read_text(encoding='utf-8'))
    lines = a.jsonl.read_text(encoding='utf-8').splitlines()
    a.out.write_text('\n'.join(apply_reviews(lines, items, a.reviewer)) + '\n', encoding='utf-8')
    r = agreement(items)
    print(f"시트 {len(items)}건 중 채점 {r['scored']}건 -> {a.out}")
    if r['scored']:
        print(f"assistant 잠정 vs 사람 일치 {r['agree']}/{r['scored']} = {r['rate']:.1%}")
    for d in r['disagreements']:
        print('  불일치', *d)


if __name__ == '__main__':
    main()
