"""완료 판정의 사람 승인·견적·재사용 사례 저장 경계. 가격·재고는 저장하지 않는다."""
from copy import deepcopy

from psycopg.types.json import Jsonb

from backend import auth

FORBIDDEN = {'price', 'price_breaks', 'stock', 'availability', 'product_url', 'fetched_at'}
APPROVABLE = {'IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT'}


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
                'candidate': deepcopy(candidate), 'evidence': deepcopy(result.get('evidence') or [])}
    assert_no_price_data(snapshot)
    return snapshot


class QuoteService:
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
            snapshot = approval_snapshot(row[1] or {}, candidate_part, verdict)
            approval = conn.execute('INSERT INTO approvals(user_id,message_id,snapshot) VALUES (%s,%s,%s) RETURNING id,created_at',
                                    (user_id, message_id, Jsonb(snapshot))).fetchone()
            case = conn.execute('INSERT INTO approved_cases(user_id,approval_id,snapshot) VALUES (%s,%s,%s) RETURNING id',
                                (user_id, approval[0], Jsonb(snapshot))).fetchone()
            return {'id': approval[0], 'message_id': message_id, 'candidate_part': candidate_part,
                    'verdict': snapshot['candidate']['verdict'], 'case_id': case[0], 'created_at': approval[1]}

    def create_quote(self, user_id: int, approval_id: int, quantity: int):
        with auth.connection() as conn:
            row = conn.execute('SELECT snapshot FROM approvals WHERE id=%s AND user_id=%s', (approval_id, user_id)).fetchone()
            if row is None:
                raise QuoteNotFound
            snapshot = deepcopy(row[0])
            assert_no_price_data(snapshot)
            part = snapshot['candidate']['part']
            quote = conn.execute('INSERT INTO quotes(user_id,approval_id,part_number,quantity,snapshot) VALUES (%s,%s,%s,%s,%s) RETURNING id,created_at',
                                 (user_id, approval_id, part, quantity, Jsonb(snapshot))).fetchone()
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
            rows = conn.execute('SELECT id,approval_id,snapshot,created_at FROM approved_cases WHERE user_id=%s ORDER BY id DESC', (user_id,)).fetchall()
            return [{'id': r[0], 'approval_id': r[1], 'candidate_part': r[2]['candidate']['part'],
                     'verdict': r[2]['candidate']['verdict'], 'created_at': r[3]} for r in rows]

    def delete_case(self, user_id: int, case_id: int):
        with auth.connection() as conn:
            if conn.execute('DELETE FROM approved_cases WHERE id=%s AND user_id=%s RETURNING id', (case_id, user_id)).fetchone() is None:
                raise QuoteNotFound
