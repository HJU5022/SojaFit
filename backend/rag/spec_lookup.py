"""부품 사양 표(part_specifications, db/011) 조회: 품번 하나의 사양 행, 숫자 조건에 맞는 부품 찾기.

- 역할: MCP 서버(`get_part_specs`, `find_parts_by_specs`)가 import하는 조회 함수 두 개. 연결은 부르는 쪽이 넘긴다.
  - `part_specs`: 품번(대소문자 무시)의 모든 행을 분류·값·단위·시험 조건·인용(문서 파일 이름, 쪽, 표, 행, 청크 순번)과 함께 돌려준다.
  - `find_candidates`: 조건마다 "그 품번의 행 하나 이상이 채우는가"만 보고, 모든 조건을 채운 품번을 모두 줄 세운 뒤
    limit개까지 돌려준다(원래 부품과 같은 패키지 → 같은 분류 → 기준에 가까운 순 → 품번 순).
- 하지 않는 일: 판정 5종과 대체 가능 여부(`backend/judge/`, AGENTS 지킬 것 7), 단위 환산(값은 이미 SI), 시험 조건 맞추기,
  LLM 호출, 표 적재(`pipeline/specs.py load`). 비교는 행을 거르는 `>=`·`<=`와 순서를 정하는 비율(값/기준)뿐이다.
- 출처: db/schema/table-definition.md 5.7, ADR 0013, SPEC.md 8.7

[주의] 표에 없는 값은 "조건 불충족"이 아니라 "문서로 확인 안 됨"이다(ADR 0013이 애매한 값을 뺐다). 여기서 빠진 품번을
불충족으로 판정하지 않는다. 시험 조건(test_condition)이 다른 행도 같은 코드면 함께 비교하므로, 조건 차이는 judge가 본다.
"""
import os
import re
from urllib.parse import unquote, urlparse

# 5.7·ADR 0013의 17개 + PACKAGE(패키지 이름, text_value)
CODES = ('VRRM', 'IF_AV', 'IFSM', 'VF', 'IR', 'TRR', 'VZ', 'PD', 'CJ', 'TJ_MAX',
         'VR', 'VRWM', 'VBR', 'VC', 'IPP', 'PPPM', 'VESD', 'PACKAGE')
SLOTS = {'min': 'minimum_value', 'typ': 'typical_value', 'max': 'maximum_value'}  # 조건의 slot → 열 이름(SQL에 넣는 글자는 이 표 값뿐)
# [왜] 적재 규칙(pipeline/specs.py)이 최소·대표·최대 표시 없는 정격 칸은 최대로, 정전용량은 대표로 넣었다. slot을 안 주면 같은 자리를 본다
DEFAULT_SLOT = {'CJ': 'typ'}

_COLUMNS = ('s.part_number, s.category, s.parameter_code, s.minimum_value, s.typical_value, s.maximum_value, s.text_value,'
            ' s.normalized_unit, s.source_value_text, s.test_condition, d.source_url, s.page_number, s.table_name,'
            ' s.row_label, s.chunk_index')
_FROM = ' FROM part_specifications s JOIN source_documents d ON d.id = s.document_id'


def _num(v):
    return None if v is None else float(v)  # [왜] NUMERIC은 Decimal로 온다. MCP 응답(JSON)에 숫자로 싣는다


def _row(r):
    """조회 열(_COLUMNS 순서) → 사양 한 줄 dict."""
    return {'part': r[0], 'category': r[1], 'code': r[2], 'min': _num(r[3]), 'typ': _num(r[4]), 'max': _num(r[5]), 'text': r[6], 'unit': r[7],
            'source_value_text': r[8], 'test_condition': r[9],
            # 인용: 문서 파일 이름은 출처 URL 끝(retrieve.corpus_known과 같은 방식). 사용자에게 보이는 근거는 이 위치의 원본 청크다
            'citation': {'document': unquote(os.path.basename(urlparse(r[10]).path)), 'page': r[11], 'table': r[12],
                         'row': r[13], 'chunk_index': r[14]}}


def part_specs(conn, part, codes=None):
    """품번 하나(대소문자 무시)의 사양 행 목록. codes를 주면 그 코드만. 코드·행 순서로 정렬한다."""
    sql, params = f'SELECT {_COLUMNS}{_FROM} WHERE upper(s.part_number) = upper(%s)', [part]
    if codes is not None:
        sql += ' AND s.parameter_code = ANY(%s)'
        params.append(list(codes))
    return [_row(r) for r in conn.execute(sql + ' ORDER BY s.parameter_code, s.id', params)]


def _norm_package(name):
    return re.sub(r'[^A-Z0-9]', '', (name or '').upper())  # 영문 · 숫자만(아래 SQL의 패키지 거르기와 같은 규칙)


def _ratio(cond, row):
    """조건을 채운 행 값이 기준에서 얼마나 먼지(1이면 기준과 같고 클수록 멂). 이상은 값/기준, 이하는 기준/값.

    기준이나 값이 0 이하라 비율을 못 내면 1(순서에 영향 없음)이다. 채운 행의 비율은 늘 1 이상이라 가장 먼 조건을 고를 때 묻힌다.
    """
    v = row[cond.get('slot') or DEFAULT_SLOT.get(cond['code'], 'max')]  # SQL이 이 칸으로 걸렀으므로 값이 있다
    ratios = ([v / cond['gte']] if 'gte' in cond and cond['gte'] > 0 else []) + ([cond['lte'] / v] if 'lte' in cond and v > 0 else [])
    return max(ratios, default=1.0)


def find_candidates(conn, conditions, category=None, package=None, limit=50, original_packages=None, original_category=None):
    """모든 조건을 채운 품번 목록(모두 줄 세운 뒤 limit개까지).

    - conditions: [{"code": "VRRM", "gte": 40}, {"code": "VZ", "slot": "min", "gte": 3.42}, ...]. 값은 SI 단위(V, A, W, s, F, degC).
      slot은 min|typ|max(기본 max, CJ는 typ). gte(이상)·lte(이하) 중 하나 이상, 둘 다 주면 둘 다 채워야 한다(경계 포함).
    - 한 조건은 그 품번의 행 하나 이상이 채우면 된다. 조건마다 다른 행이어도 된다(제너 VZ 최소 행과 최대 행).
    - category: 분류 이름과 같아야 한다(예: zener-diode). package: 패키지 이름이 같아야 한다(대소문자 · 하이픈 · 공백 무시, 'SMA'는 SMAF에 걸리지 않음).
    - 순서(11-06 정운 결정): 원래 부품의 패키지(original_packages 중 하나와 이름이 같음) → 원래 부품의 분류(original_category)
      → 기준에 가까운 것 → 품번 순. 줄 세우기는 조건을 채운 품번 전부에 하고 그 뒤 limit에서 자른다(4,081개 중 63번째 1N5817이 잘리던 문제).
    - 반환: [{"part", "category", "packages", "matches": 조건을 채운 행(part_specs와 같은 모양)}]. 값 비교는 행 거르기와 순서뿐이고 판정이 아니다.
    """
    checks, params = [], []
    for c in conditions:
        col = SLOTS[c.get('slot') or DEFAULT_SLOT.get(c['code'], 'max')]
        bounds = [f's.{col} >= %s'] * ('gte' in c) + [f's.{col} <= %s'] * ('lte' in c)
        checks.append(f"(s.parameter_code = %s AND {' AND '.join(bounds)})")
        params += [c['code']] + [c[k] for k in ('gte', 'lte') if k in c]
    # [왜] 조건마다 참·거짓 열을 하나씩 뽑아, 품번별로 "모든 조건이 한 번 이상 참"인지 아래에서 센다
    sql = f"SELECT {_COLUMNS}, {', '.join(checks)}{_FROM} WHERE s.parameter_code = ANY(%s)"
    params.append(list({c['code'] for c in conditions}))
    if category is not None:
        sql += ' AND s.category = %s'
        params.append(category)
    if package is not None:
        # [왜] 이름이 같을 때만 같은 패키지다. 부분 일치면 SMA가 다른 패키지 SMAF까지 잡는다(11-05, 564개 중 36개)
        # [왜] 영문 · 숫자만 남겨 비교한다. 데이터시트마다 'DO-214AC' · 'DO214AC'처럼 하이픈을 다르게 적는다
        sql += (" AND EXISTS (SELECT 1 FROM part_specifications p WHERE upper(p.part_number) = upper(s.part_number)"
                " AND p.parameter_code = 'PACKAGE' AND regexp_replace(upper(p.text_value), '[^A-Z0-9]', '', 'g') = %s)")
        params.append(_norm_package(package))
    parts = {}  # 품번 대문자 → 결과 한 개
    met = {}  # 품번 대문자 → {채운 조건 번호: 그 조건을 채운 행 중 기준에 가장 가까운 비율}
    for r in conn.execute(sql + ' ORDER BY s.parameter_code, s.id', params):
        hits = [i for i, ok in enumerate(r[15:]) if ok]
        if not hits:
            continue
        key, row = r[0].upper(), _row(r)
        parts.setdefault(key, {'part': r[0], 'category': r[1], 'packages': [], 'matches': []})['matches'].append(row)
        near = met.setdefault(key, {})
        for i in hits:
            near[i] = min(near.get(i, float('inf')), _ratio(conditions[i], row))
    found = {k: parts[k] for k in parts if len(met[k]) == len(conditions)}
    if found:
        # [왜] 패키지 순위를 자르기 전에 보려고 조건을 채운 품번 전부의 패키지를 읽는다(질의 한 번)
        rows = conn.execute("SELECT part_number, text_value FROM part_specifications WHERE parameter_code = 'PACKAGE'"
                            ' AND upper(part_number) = ANY(%s) ORDER BY id', (list(found),))
        for part, name in rows:
            found[part.upper()]['packages'].append(name)
    want = {_norm_package(p) for p in original_packages or []} - {''}

    def order(key):
        p = found[key]
        # [왜] 조건이 여럿이면 가장 먼 조건의 비율로 본다. 평균이면 한 값만 크게 넘는 부품(1000 V짜리)이 다른 값에 가려 앞에 온다
        far = max(met[key].values())
        return (bool(want) and not want & {_norm_package(x) for x in p['packages']},
                original_category is not None and p['category'] != original_category, far, key)
    # [왜] 품번 순서는 DB 정렬 규칙(collation)에 따라 달라질 수 있어 파이썬 글자 순서로 정한다(로컬·Supabase 같은 순서)
    return [found[k] for k in sorted(found, key=order)][:limit]

