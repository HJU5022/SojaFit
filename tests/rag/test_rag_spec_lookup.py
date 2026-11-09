"""사양 찾기(`backend.rag.spec_lookup.find_candidates`)의 줄 세우기를 가짜 연결로 DB 없이 확인한다.

- 역할: 조건을 채운 품번 전부를 원래 부품과 같은 패키지 → 같은 분류 → 기준에 가까운 순 → 품번 순으로 줄 세운 뒤 자르는지,
  조건이 여럿이면 가장 먼 조건의 비율로 줄 세우는지 본다.
- 하지 않는 일: 사양 표 SQL · 적재 · DB 조회(사양 표는 11-09에 지웠다, ADR 0016). 카드 찾기가 같은 규칙인지는 `test_card_find.py`가 본다.
- 출처: ADR 0013(대체됨 → 0016), SPEC.md 8.7
"""
from backend.rag import spec_lookup


# --- 찾기 순위(가짜 연결, DB 없음) ---

class FakeConn:
    """find_candidates의 두 질의(조건 행, 패키지 행)에 정해진 행을 돌려준다. 행은 _COLUMNS 15칸 + 조건별 참·거짓이다."""

    def __init__(self, parts, conditions):
        self.parts, self.conditions = parts, conditions  # parts: {품번: (분류, [패키지], {코드: 최대값})}

    def execute(self, sql, params):
        if "parameter_code = 'PACKAGE'" in sql and sql.lstrip().startswith('SELECT part_number'):
            return [(p, pkg) for p, (_, pkgs, _) in self.parts.items() if p.upper() in params[0] for pkg in pkgs]
        rows = []
        for p, (cat, _, values) in sorted(self.parts.items()):
            for code, v in values.items():
                hits = [c['code'] == code and v >= c.get('gte', v) and v <= c.get('lte', v) for c in self.conditions]
                rows.append((p, cat, code, None, None, v, None, 'V', str(v), None, f'https://x.test/{p}.pdf', 1, 'T', p, 1, *hits))
        return rows


PARTS = {'1N4001': ('standard-rectifier', ['DO-41'], {'VRRM': 50.0}),
         '1N5817': ('schottky-rectifier', ['DO-204AL', 'DO-41'], {'VRRM': 20.0}),
         '1N5819': ('schottky-rectifier', ['DO-41'], {'VRRM': 40.0}),
         'AAA1': ('standard-rectifier', ['SMA'], {'VRRM': 1000.0}),
         'SS14': ('schottky-rectifier', ['SMA', 'DO-214AC'], {'VRRM': 40.0}),
         'ZZ1': ('schottky-rectifier', ['SMA'], {'VRRM': 10.0})}  # 조건 밖


def test_find_ranks_all_matches_before_the_limit():
    """품번 순으로 자르면 앞의 1N4001만 남지만, 원래 부품과 같은 패키지 → 같은 분류 → 기준에 가까운 순으로 모두 줄 세운 뒤 자른다(SPEC 8.3 찾기 순위)."""
    cond = [{'code': 'VRRM', 'gte': 15}]
    conn = FakeConn(PARTS, cond)
    top = spec_lookup.find_candidates(conn, cond, limit=1, original_packages=['DO-214AC'], original_category='schottky-rectifier')
    assert [p['part'] for p in top] == ['SS14'] and top[0]['packages'] == ['SMA', 'DO-214AC']
    # 패키지가 분류보다 먼저: 같은 패키지 · 다른 분류(AAA1) → 다른 패키지 · 같은 분류(기준 15 V에 가까운 순) → 둘 다 다름
    ranked = spec_lookup.find_candidates(conn, cond, original_packages=['sma'], original_category='schottky-rectifier')
    assert [p['part'] for p in ranked] == ['SS14', 'AAA1', '1N5817', '1N5819', '1N4001']
    # 원래 부품을 모르면 기준에 가까운 순(20/15 < 40/15 = 40/15 < 50/15 < 1000/15), 같으면 품번 순
    assert [p['part'] for p in spec_lookup.find_candidates(conn, cond)] == ['1N5817', '1N5819', 'SS14', '1N4001', 'AAA1']


def test_find_rank_uses_the_farthest_condition():
    """조건이 여럿이면 조건마다 '값/기준'(이하면 '기준/값') 중 가장 큰 비율로 줄 세운다. 한 값만 크게 넘는 부품이 뒤로 간다."""
    cond = [{'code': 'VRRM', 'gte': 20}, {'code': 'IF_AV', 'lte': 2.0}]
    parts = {'A1': ('x', [], {'VRRM': 21.0, 'IF_AV': 0.1}),   # 최대 비율 2/0.1 = 20
             'B1': ('x', [], {'VRRM': 60.0, 'IF_AV': 1.0})}   # 최대 비율 60/20 = 3
    assert [p['part'] for p in spec_lookup.find_candidates(FakeConn(parts, cond), cond)] == ['B1', 'A1']
