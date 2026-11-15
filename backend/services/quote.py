"""완료 판정의 사람 승인·견적·재사용 사례 저장 경계. 가격·재고는 저장하지 않는다."""
import re
from copy import deepcopy

from psycopg.types.json import Jsonb

from backend import auth

FORBIDDEN = {'price', 'price_breaks', 'stock', 'availability', 'product_url', 'fetched_at'}
APPROVABLE = {'IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT'}


# [왜] 판정 결과의 품번은 모델이 읽은 이름을 질문에 쓴 대로 보여 준다('TSC 1N4007G', '1N4148 A0G', 판정 시험이 고정한 계약).
#      견적의 part_number는 DB 규칙(공백 없는 영문 · 숫자 · . _ + / -)이라 둘이 어긋나면 승인 · 견적이 422 · 저장 실패였다(11-10 배포 점검).
#      그래서 승인할 때 표시 이름은 그대로 두고 식별용 품번을 따로 만든다. 제조사 이름 규칙은 multi_agent/agents/part_names.py의 MAKER와 같게 둔다
MAKER = re.compile(r'^\s*(?:TSC|Taiwan\s+Semiconductor)\s+', re.I)
PART_NUMBER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}')


class QuoteNotFound(Exception):
    pass


class InvalidApproval(Exception):
    pass


def assert_no_price_data(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN:
                raise InvalidApproval('가격·재고 데이터는 저장할 수 없습니다.')
            assert_no_price_data(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_price_data(item)


def part_number(display: str) -> str:
    """표시 이름('TSC 1N4007G')에서 견적용 식별 품번('1N4007G')을 만든다: 제조사 이름을 떼고 남은 공백(주문 코드)은 '-'로 잇는다.

    Raises:
        InvalidApproval: 그래도 DB 품번 규칙에 안 맞으면(호출자가 409로 거절).
    """
    number = re.sub(r'\s+', '-', MAKER.sub('', display or '').strip())
    if not PART_NUMBER.fullmatch(number):
        raise InvalidApproval('견적에 쓸 수 있는 품번이 아닙니다.')
    return number


def approval_snapshot(result: dict, candidate_part: str, verdict: str) -> dict:
    judgement = result.get('judgement') if isinstance(result, dict) else None
    if not isinstance(judgement, dict):
        raise InvalidApproval('승인할 판정이 없습니다.')
    candidates = [item for key in ('results', 'shown') for item in judgement.get(key, []) if isinstance(item, dict)]
    candidate = next((item for item in candidates
                      if item.get('part') == candidate_part and item.get('verdict') == verdict), None)
    if candidate is None or verdict not in APPROVABLE:
        raise InvalidApproval('승인 가능한 후보 판정이 아닙니다.')
    missing = candidate.get('missing') or []
    checks = candidate.get('checks') or []
    has_unverified_required = any(isinstance(check, dict) and check.get('tier') == 'required'
                                  and check.get('result') == 'unverified' for check in checks)
    if missing or has_unverified_required:
        raise InvalidApproval('필수 조건을 확인하지 않아 승인할 수 없습니다.')
    snapshot = {'answer': result.get('answer', ''), 'question_type': result.get('question_type', ''),
                'candidate': {**deepcopy(candidate), 'part_number': part_number(candidate_part)},  # 승인할 때 만들어 견적이 못 쓰는 품번의 승인을 막는다
                'evidence': deepcopy(result.get('evidence') or [])}
    assert_no_price_data(snapshot)
    return snapshot


class QuoteService:
    def list_approvals(self, user_id: int, message_id: int):
        with auth.connection() as conn:
            if conn.execute("SELECT 1 FROM messages m JOIN threads t ON t.id=m.thread_id JOIN projects p ON p.id=t.project_id "
                            "WHERE m.id=%s AND m.role='assistant' AND p.user_id=%s", (message_id, user_id)).fetchone() is None:
                raise QuoteNotFound
            rows = conn.execute('SELECT a.id,a.message_id,a.candidate_part,a.verdict,c.id,a.created_at,a.part_number FROM approvals a '
                                'JOIN approved_cases c ON c.approval_id=a.id AND c.user_id=a.user_id '
                                'WHERE a.message_id=%s AND a.user_id=%s ORDER BY a.id', (message_id, user_id)).fetchall()
            return [{'id': r[0], 'message_id': r[1], 'candidate_part': r[2], 'verdict': r[3],
                     'case_id': r[4], 'created_at': r[5], 'part_number': r[6] or part_number(r[2])} for r in rows]

    def approve(self, user_id: int, message_id: int, candidate_part: str, verdict: str):
        with auth.connection() as conn:
            row = conn.execute("""SELECT r.status,r.safe_result FROM messages m
                JOIN runs r ON r.id=m.run_id AND r.thread_id=m.thread_id
                JOIN threads t ON t.id=m.thread_id JOIN projects p ON p.id=t.project_id
                WHERE m.id=%s AND m.role='assistant' AND p.user_id=%s FOR UPDATE OF r""", (message_id, user_id)).fetchone()
            if row is None:
                raise QuoteNotFound
            if row[0] != 'completed':
                raise InvalidApproval('완료된 판정만 승인할 수 있습니다.')
            if conn.execute('SELECT 1 FROM approvals a JOIN approved_cases c ON c.approval_id=a.id AND c.user_id=a.user_id '
                            'WHERE a.message_id=%s AND a.user_id=%s', (message_id, user_id)).fetchone():
                raise InvalidApproval('이미 승인되었습니다.')
            snapshot = approval_snapshot(row[1] or {}, candidate_part, verdict)
            candidate = snapshot['candidate']
            # [왜] 승인 스냅샷은 approvals 한 곳에만 둔다(견적 · 승인 사례에 복사하지 않는다). 목록 · 견적이 읽는 값 3개는 칸으로 같이 저장한다
            approval = conn.execute('INSERT INTO approvals(user_id,message_id,snapshot,candidate_part,verdict,part_number) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,created_at',
                                    (user_id, message_id, Jsonb(snapshot), candidate['part'], candidate['verdict'], candidate['part_number'])).fetchone()
            case = conn.execute('INSERT INTO approved_cases(user_id,approval_id) VALUES (%s,%s) RETURNING id', (user_id, approval[0])).fetchone()
            return {'id': approval[0], 'message_id': message_id, 'candidate_part': candidate_part,
                      'verdict': snapshot['candidate']['verdict'], 'case_id': case[0], 'created_at': approval[1],
                      'part_number': candidate['part_number']}

    def create_quote(self, user_id: int, approval_id: int, quantity: int):
        with auth.connection() as conn:
            row = conn.execute("SELECT a.part_number,a.candidate_part,a.snapshot #>> '{candidate,part}' FROM approvals a "
                               'JOIN approved_cases c ON c.approval_id=a.id AND c.user_id=a.user_id '
                               'WHERE a.id=%s AND a.user_id=%s FOR SHARE OF c', (approval_id, user_id)).fetchone()
            if row is None:
                raise QuoteNotFound
            part = row[0] or part_number(row[1] or row[2] or '')  # [주의] expand 뒤 contract 전에 옛 코드가 넣은 승인은 칸 3개가 모두 NULL이라 스냅샷의 후보 이름으로 폴백해 같은 규칙으로 계산한다. 견적에는 스냅샷을 복사하지 않는다
            quote = conn.execute('INSERT INTO quotes(user_id,approval_id,part_number,quantity) VALUES (%s,%s,%s,%s) RETURNING id,created_at',
                                 (user_id, approval_id, part, quantity)).fetchone()
            return {'id': quote[0], 'approval_id': approval_id, 'part_number': part, 'quantity': quantity, 'created_at': quote[1]}

    def list_quotes(self, user_id: int, project_id: int):
        with auth.connection() as conn:
            if conn.execute('SELECT 1 FROM projects WHERE id=%s AND user_id=%s', (project_id, user_id)).fetchone() is None:
                raise QuoteNotFound
            rows = conn.execute("""SELECT q.id,q.approval_id,q.part_number,q.quantity,q.created_at FROM quotes q
                JOIN approvals a ON a.id=q.approval_id JOIN messages m ON m.id=a.message_id
                JOIN threads t ON t.id=m.thread_id WHERE q.user_id=%s AND t.project_id=%s ORDER BY q.id""", (user_id, project_id)).fetchall()
            return [{'id': r[0], 'approval_id': r[1], 'part_number': r[2], 'quantity': r[3], 'created_at': r[4]} for r in rows]

    def list_cases(self, user_id: int):
        with auth.connection() as conn:
            rows = conn.execute("""SELECT c.id,c.approval_id,COALESCE(a.candidate_part,a.snapshot #>> '{candidate,part}'),COALESCE(a.verdict,a.snapshot #>> '{candidate,verdict}'),c.created_at FROM approved_cases c
                JOIN approvals a ON a.id=c.approval_id WHERE c.user_id=%s ORDER BY c.id DESC""", (user_id,)).fetchall()
            return [{'id': r[0], 'approval_id': r[1], 'candidate_part': r[2], 'verdict': r[3], 'created_at': r[4]} for r in rows]

    def delete_case(self, user_id: int, case_id: int):
        with auth.connection() as conn:
            if conn.execute('DELETE FROM approved_cases WHERE id=%s AND user_id=%s RETURNING id', (case_id, user_id)).fetchone() is None:
                raise QuoteNotFound
