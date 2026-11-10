"""서비스 DB 표 정의서(db/schema/table-definition.md)와 ERD(db/schema/erd.md)를 실제 DB의 pg_catalog에서 만든다.

사용(저장소 루트): DATABASE_URL=<읽기만 하는 연결> uv run python scripts/db/gen_schema_docs.py [--out-dir DIR] [--check]
- 기본 출력은 db/schema/. --out-dir로 다른 곳에 쓸 수 있다(시험이 임시 폴더에 쓴다). --check는 파일을 쓰지 않고 이미 있는 문서가 DB와 같은지만 본다(다르면 종료 코드 1).
- 읽는 것: `public`과 `sojafit_agent`의 서비스 표 칸 · PK · FK(ON DELETE) · UNIQUE · CHECK · 인덱스 · 트리거. 쓰기 · DDL은 하지 않는다(읽기 전용 트랜잭션).
- 코퍼스 4표와 LangGraph 라이브러리 표는 문서에 별도 절로 이름만 적는다(EXCLUDED). 그 밖의 표가 DB에 있는데 아래 TABLES에 설명이 없으면 멈춘다.
- [왜] 문서를 손으로 쓰면 SQL과 어긋난다(옛 정의서가 그랬다). 구조는 DB에서 읽고, 사람이 써야 하는 것(표 목적 · 칸 의미)만 TABLES에 둔다.
- [주의] 표나 칸을 더하거나 지우면 TABLES도 같이 고친다. 빠진 설명 · 남은 설명은 오류로 멈춘다(문서가 조용히 틀리지 않게 하려는 것).
- [주의] 이 파일은 비밀번호 · 접속 문자열을 찍지 않는다. 출력 문서에는 시각 · 호스트가 없어 같은 DB 구조면 글자까지 같다.
"""
import argparse
import os
import re
import sys
from pathlib import Path

import psycopg

OUT_DIR = Path(__file__).resolve().parents[2] / 'db' / 'schema'
SCHEMAS = ('public', 'sojafit_agent')
MARKER = '<!-- 자동 생성: scripts/db/gen_schema_docs.py. 직접 고치지 않는다(표 설명은 그 파일의 TABLES, 구조는 DB). -->'

# 문서에서 이름만 적는 표(코퍼스 · LangGraph 라이브러리). 서비스 표가 아니라 설명 없이 둔다
EXCLUDED = {
    'public': ('source_documents', 'document_chunks', 'chunk_embeddings', 'chunk_embedding_bits'),
    'sojafit_agent': ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes', 'checkpoint_migrations',
                      'store', 'store_vectors', 'store_migrations', 'vector_migrations'),
}

# 서비스 표: '스키마.표' -> (목적 한 줄, {칸: 의미}). 순서가 문서의 표 순서다
TABLES = {
    'public.users': ('계정', {
        'id': '계정 번호(내부 키)',
        'login_id': '로그인 이메일(소문자). 구글 가입도 같은 칸에 이메일 저장',
        'password_hash': "scrypt 해시. Google 전용은 'google-login-only', 로컬 데모 버튼은 'demo-button-login-only' 표식(비밀번호 로그인 불가)",
        'is_active': '비활성이면 로그인 · 세션 불가',
        'created_at': '가입 시각',
        'updated_at': '수정 시각',
        'role': 'admin | user',
    }),
    'public.auth_sessions': ('로그인 세션', {
        'token_hash': '세션 토큰의 SHA-256(원문 저장 안 함)',
        'user_id': '소유 계정',
        'expires_at': '절대 만료 시각',
        'last_seen_at': '마지막 사용 시각(유휴 만료 판단)',
    }),
    'public.auth_login_attempts': ('계정별 로그인 실패 · 잠금', {
        'login_hash': '이메일의 SHA-256',
        'failed_count': '집계 창 안의 실패 횟수',
        'locked_until': '잠금 끝 시각',
        'window_started_at': '15분 집계 창 시작',
    }),
    'public.auth_login_ip_attempts': ('IP별 로그인 실패 · 잠금', {
        'ip_hash': '클라이언트 IP 키의 SHA-256',
        'failed_count': '실패 횟수',
        'window_started_at': '집계 창 시작',
        'locked_until': '잠금 끝',
    }),
    'public.auth_signup_attempts': ('IP별 하루 가입 요청 수(데모 모드 전용)', {
        'ip_hash': 'IP 키 해시',
        'day': 'UTC 날짜',
        'signup_count': '그날 가입 요청 수(상한 3)',
    }),
    'public.auth_google_states': ('Google OAuth 일회용 상태', {
        'state_hash': 'state의 해시',
        'browser_hash': '브라우저 쿠키 해시(다른 브라우저의 콜백 거부)',
        'verifier': 'PKCE verifier',
        'nonce': 'ID 토큰 nonce',
        'expires_at': '10분 뒤 만료',
    }),
    'public.auth_google_identities': ('Google 신원 ↔ 사용자 연결', {
        'issuer': 'https://accounts.google.com',
        'subject': 'Google 계정 식별자(sub)',
        'user_id': '연결된 계정(사용자당 1개)',
    }),
    'public.projects': ('프로젝트', {
        'id': '프로젝트 번호',
        'user_id': '소유자',
        'name': '이름(공백 제거 1~200자)',
        'source_kind': 'demo | upload',
        'demo_id': '데모 회로 이름(데모일 때만, DB가 6개 이름 목록으로 검사)',
        'created_at': '만든 시각',
        'updated_at': '이름 변경 · 대화 활동 시각',
    }),
    'public.circuits': ('프로젝트의 정규화 회로(1:1)', {
        'project_id': '프로젝트(1:1, 키)',
        'connections': '정규화한 회로(부품 · 넷 JSON)',
        'source_sha256': '원본 넷리스트 SHA-256(원문은 저장 안 함)',
        'parser_version': '회로 변환기 버전',
        'created_at': '',
    }),
    'public.threads': ('프로젝트 안의 대화', {
        'id': '대화 UUID(URL에 노출)',
        'project_id': '소속 프로젝트',
        'created_at': '만든 시각',
    }),
    'public.runs': ('질문 한 번의 실행과 공개 결과', {
        'id': 'run UUID(URL에 노출)',
        'thread_id': '소속 대화',
        'status': 'running | requires_input | completed | refused | failed',
        'safe_result': '공개 결과 JSON(answer · question_type · price_parts · interrupt · judgement · evidence). 모양을 DB CHECK 함수가 재귀 검사',
        'created_at': '시작',
        'updated_at': '마지막 변경',
    }),
    'public.messages': ('화면 대화 기록', {
        'id': '메시지 번호',
        'thread_id': '대화',
        'run_id': 'run(대화와 함께 복합 FK)',
        'role': 'user | assistant',
        'content': '질문 · 답 글',
        'created_at': '시각',
    }),
    'public.approvals': ('사람의 후보 승인(스냅샷의 유일한 사본)', {
        'id': '승인 번호',
        'user_id': '승인한 사용자',
        'message_id': '승인한 어시스턴트 메시지(고유, 메시지당 1건)',
        'candidate_part': "승인한 후보 품번의 **표시 이름**(판정 결과가 보여 준 그대로. 예 'TSC 1N4007G'). 승인 JSON에서 꺼낸 칸",
        'verdict': '승인한 판정 IDENTICAL | SPEC_EQUIVALENT | ROLE_SUFFICIENT. 승인 JSON에서 꺼낸 칸',
        'part_number': "견적용 **식별 품번**: 제조사 이름(TSC 등)을 떼고 남은 공백(주문 코드)은 '-'(예 '1N4007G', '1N4148-A0G'). 승인 JSON에서 꺼낸 칸",
        'snapshot': '승인 시점의 {answer, question_type, candidate, evidence} 증빙 JSON. **스냅샷의 유일한 사본**. 가격 · 재고 키는 CHECK 함수가 거부',
        'created_at': '승인 시각',
    }),
    'public.quotes': ('승인에서 만든 가격 없는 견적', {
        'id': '견적 번호',
        'user_id': '소유자',
        'approval_id': '근거 승인(승인당 1건)',
        'part_number': '견적 품번(공백 없는 영문 · 숫자 · . _ + / -, CHECK)',
        'quantity': '수량 1~100000',
        'created_at': '저장 시각',
    }),
    'public.approved_cases': ('화면의 승인 사례 목록(사용자가 지울 수 있는 표시 행)', {
        'id': '사례 번호',
        'user_id': '소유자',
        'approval_id': '근거 승인(고유). 후보 이름 · 판정은 approvals에서 읽는다',
        'created_at': '시각',
    }),
    'public.app_migrations': ('마이그레이션 적용 이력(우리 것)', {
        'version': '적용한 변경의 이름',
        'applied_at': '적용 시각',
        'note': '한 줄 설명',
    }),
    'sojafit_agent.threads': ('분석 서비스의 대화 상태 기계', {
        'id': '**public.threads.id와 같은 UUID이며 FK**(대화를 지우면 같이 지워짐)',
        'user_id': '소유자(CASCADE). 소유 조회를 빠르게 하려고 둔 의도된 비정규화',
        'target': '교체 대상 부품 참조(예: D1)',
        'version': '질문 차수(새 질문마다 +1)',
        'retries': '같은 질문의 재시도 횟수(상한 2)',
        'status': 'NEW | RUNNING | WAITING | DONE | FAILED',
        'created_at': '시각',
        'input_record': '현재 차수의 원문 질문 · 조건 · 재개 답(JSON)',
    }),
    'sojafit_agent.messages': ('분석 문맥용 사용자 입력 + 어시스턴트 답', {
        'id': '번호',
        'thread_id': '분석 대화',
        'role': 'user | assistant',
        'checkpoint_id': '그 답을 만든 LangGraph 체크포인트(중복 방지 고유 색인)',
        'content': "사용자는 '사용 조건: …' 접두 + 질문",
        'created_at': '시각',
    }),
    'sojafit_agent.analysis_events': ('내용 없는 운영 기록', {
        'id': 'UUID',
        'thread_id': '분석 대화',
        'version': '질문 차수',
        'request_id': 'X-Request-ID',
        'mode': 'real | demo',
        'status': '결과 상태',
        'elapsed_ms': '사람 대기 제외 실행 시간',
        'stages': '단계별 ms(내용 없음)',
        'trace_id': 'Langfuse trace id',
        'trace_delivery': 'queued 등 전달 상태',
        'created_at': '시각',
    }),
    'sojafit_agent.analysis_usage': ('사용자 · 날짜별 LLM 예약 사용량', {
        'user_id': '사용자',
        'day': 'UTC 날짜',
        'reserved_usd': '예약 비용(청구액 아님, 환불 안 함)',
        'attempts': '그날 시도 수',
        'next_allowed': '다음 허용 시각(호출 간격)',
        'reserved_tokens': '예약 토큰(상한 사용자 200,000 → 운영 1,000,000)',
    }),
    'sojafit_agent.analysis_service_usage': ('서비스 전체 날짜별 예약 토큰', {
        'day': 'UTC 날짜',
        'reserved_tokens': '서비스 전체 예약 토큰(상한 2,000,000)',
    }),
}

SHORT_TYPES = {'character varying': 'varchar', 'timestamp with time zone': 'timestamptz', 'character': 'char',
               'boolean': 'bool', 'integer': 'int', 'double precision': 'float8'}
DELETE_RULES = {'a': 'NO ACTION', 'r': 'RESTRICT', 'c': 'CASCADE', 'n': 'SET NULL', 'd': 'SET DEFAULT'}
KINDS = {'p': 'PK', 'u': 'UNIQUE', 'f': 'FK', 'c': 'CHECK'}


def entity(name):
    """mermaid 개체 이름. 두 스키마에 같은 이름(threads · messages)이 있어 sojafit_agent 쪽에 agent_를 붙인다."""
    schema, table = name.split('.')
    return table if schema == 'public' else f'agent_{table}'


def read_catalog(conn):
    """서비스 표마다 칸 · 제약 · 인덱스 · 트리거를 pg_catalog에서 읽는다. 읽기만 한다."""
    with conn.transaction():  # [주의] 열린 트랜잭션이 없는 연결에서 불러야 한다(READ ONLY는 첫 문장이어야 한다)
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SET LOCAL search_path = public")  # [왜] FK · 인덱스 정의에 붙는 스키마 접두어를 접속 설정과 무관하게 같게 한다
        return _read(conn)


def _read(conn):
    found = {}
    for oid, schema, table in conn.execute(
            "SELECT c.oid, n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('r','p') AND n.nspname = ANY(%s) ORDER BY 2, 3", (list(SCHEMAS),)).fetchall():
        if table in EXCLUDED.get(schema, ()):
            continue
        cols = conn.execute(
            "SELECT a.attnum, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, pg_get_expr(d.adbin, d.adrelid) "
            "FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
            "WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum", (oid,)).fetchall()
        names = {num: name for num, name, *_ in cols}
        cons = []
        for name, kind, definition, key, parent_schema, parent, rule in conn.execute(
                "SELECT con.conname, con.contype, pg_get_constraintdef(con.oid), con.conkey, pn.nspname, pc.relname, con.confdeltype "
                "FROM pg_constraint con LEFT JOIN pg_class pc ON pc.oid = con.confrelid LEFT JOIN pg_namespace pn ON pn.oid = pc.relnamespace "
                "WHERE con.conrelid = %s AND con.contype IN ('p','u','f','c')", (oid,)).fetchall():
            cons.append({'name': name, 'kind': KINDS[kind], 'def': definition, 'cols': [names[k] for k in key or ()],
                         'parent': f'{parent_schema}.{parent}' if parent else None, 'rule': DELETE_RULES.get(rule)})
        cons.sort(key=lambda c: (list(KINDS.values()).index(c['kind']), c['name']))
        idx = [(name, re.sub(r'^.* USING ', '', definition)) for name, definition in conn.execute(
            "SELECT ic.relname, pg_get_indexdef(i.indexrelid) FROM pg_index i JOIN pg_class ic ON ic.oid = i.indexrelid "
            "WHERE i.indrelid = %s ORDER BY ic.relname", (oid,)).fetchall()]
        trig = conn.execute("SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger WHERE tgrelid = %s AND NOT tgisinternal ORDER BY tgname", (oid,)).fetchall()
        found[f'{schema}.{table}'] = {'cols': [(n, t, nn, d) for _, n, t, nn, d in cols], 'cons': cons, 'idx': idx, 'trig': trig}
    return found


def check_descriptions(found):
    """DB의 서비스 표 · 칸과 TABLES가 정확히 같은 목록인지 본다. 다르면 무엇이 빠지고 남았는지 적어 멈춘다."""
    problems = [f'설명이 없는 표(DB에만 있음): {t}' for t in found if t not in TABLES]
    problems += [f'DB에 없는 표(TABLES에만 있음): {t}' for t in TABLES if t not in found]
    for table, info in found.items():
        if table not in TABLES:
            continue
        described = TABLES[table][1]
        actual = [c[0] for c in info['cols']]
        problems += [f'{table}: 설명이 없는 칸 {c}' for c in actual if c not in described]
        problems += [f'{table}: DB에 없는 칸 설명 {c}' for c in described if c not in actual]
    if problems:
        raise SystemExit('TABLES와 DB가 다릅니다. scripts/db/gen_schema_docs.py의 TABLES를 고치세요.\n' + '\n'.join(problems))


def short_type(text):
    base = re.match(r'[a-z ]+', text)[0].strip()
    return (SHORT_TYPES.get(base, base) + text[len(base):]).replace(' ', '_')


def cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def render_erd(found):
    lines = ['# DB ERD', '', MARKER, '',
             '- 실제 DB에서 읽은 서비스 표의 그림이다. **모든 선이 DB의 FK**이고, 선 이름은 `FK 칸 (ON DELETE 규칙)`이다. 표마다 하는 일 · 칸 설명은 [table-definition.md](table-definition.md).',
             '- `agent_*`는 `sojafit_agent` 스키마의 표를 줄여 쓴 이름이다(`public`과 이름이 같은 표가 있어서). `PK` 기본 키, `FK` 외래 키, `UK` 단독 UNIQUE 칸.',
             '', '```mermaid', 'erDiagram']
    edges, linked = [], set()
    for table, info in found.items():
        unique_sets = [set(c['cols']) for c in info['cons'] if c['kind'] in ('PK', 'UNIQUE')]
        notnull = {c[0]: c[2] for c in info['cols']}
        for con in info['cons']:
            if con['kind'] != 'FK':
                continue
            parent_side = '||' if all(notnull[c] for c in con['cols']) else '|o'
            child_side = 'o|' if set(con['cols']) in unique_sets else 'o{'
            edges.append(f'    {entity(con["parent"])} {parent_side}--{child_side} {entity(table)} : "{"+".join(con["cols"])} ({con["rule"]})"')
            linked |= {table, con['parent']}
    lines += sorted(edges) + ['']
    for table, info in found.items():
        pk = {c for con in info['cons'] if con['kind'] == 'PK' for c in con['cols']}
        fk = {c for con in info['cons'] if con['kind'] == 'FK' for c in con['cols']}
        uk = {c for con in info['cons'] if con['kind'] == 'UNIQUE' and len(con['cols']) == 1 for c in con['cols']}
        lines.append(f'    {entity(table)} {{')
        for name, typ, _, _ in info['cols']:
            keys = ', '.join(k for k, s in (('PK', pk), ('FK', fk), ('UK', uk)) if name in s)
            lines.append(f'        {short_type(typ)} {name}' + (f' {keys}' if keys else ''))
        lines.append('    }')
    lines += ['```', '']
    alone = [t for t in found if t not in linked]
    lines += ['## 선이 없는 표', '', '- 다른 표와 FK가 없다(해시 키 · 날짜 키로만 식별): ' + ' · '.join(f'`{t}`' for t in alone), '']
    lines += render_library_section()
    return '\n'.join(lines)


def render_library_section():
    lines = ['## 코퍼스 · LangGraph 표(이 문서 범위 밖)', '',
             '서비스 표가 아니라 이 문서의 그림 · 정의에 넣지 않는다. 이름만 적는다.', '']
    lines += ['- 코퍼스(`public`, `db/002` · `009`): ' + ' · '.join(f'`{t}`' for t in EXCLUDED['public'])]
    lines += ['- LangGraph 라이브러리(`sojafit_agent`, `PostgresSaver` · `PostgresStore`가 만든다): ' + ' · '.join(f'`{t}`' for t in EXCLUDED['sojafit_agent']), '']
    return lines


def render_definition(found):
    lines = ['# SojaFit DB 표 정의서', '', MARKER, '',
             '- 구조(타입 · NULL · 기본값 · 제약 · 인덱스)는 실제 DB에서 읽은 값이고, 목적 · 칸 의미는 `scripts/db/gen_schema_docs.py`의 `TABLES`에 있다. 그림은 [erd.md](erd.md).',
             '- FK 정의에 `ON DELETE`가 없으면 `NO ACTION`이다. 서비스 표 ' + str(len(found)) + '개.', '',
             '| 스키마.표 | 목적 |', '|---|---|']
    lines += [f'| `{t}` | {cell(TABLES[t][0])} |' for t in found]
    lines.append('')
    for table, info in found.items():
        purpose, meaning = TABLES[table]
        lines += [f'## `{table}`', '', f'- **목적**: {purpose}', '', '| 칸 | 타입 | NULL | 기본값 | 의미 |', '|---|---|---|---|---|']
        lines += [f'| `{n}` | {cell(t)} | {"NOT NULL" if nn else "NULL"} | {cell(d or "")} | {cell(meaning[n])} |' for n, t, nn, d in info['cols']]
        lines += ['', '| 제약 | 종류 | 정의 |', '|---|---|---|']
        lines += [f'| `{c["name"]}` | {c["kind"]} | `{cell(c["def"])}` |' for c in info['cons']]
        lines += ['', '| 인덱스 | 정의 |', '|---|---|']
        lines += [f'| `{n}` | `{cell(d)}` |' for n, d in info['idx']]
        if info['trig']:
            lines += ['', '| 트리거 | 정의 |', '|---|---|']
            lines += [f'| `{n}` | `{cell(d)}` |' for n, d in info['trig']]
        lines.append('')
    lines += render_library_section()
    return '\n'.join(lines)


def generate(conn):
    """연결 하나에서 {파일 이름: 글}을 만든다. TABLES와 DB가 다르면 SystemExit."""
    found = read_catalog(conn)
    check_descriptions(found)
    found = {t: found[t] for t in TABLES}  # 문서의 표 순서 = TABLES 순서
    return {'erd.md': render_erd(found).rstrip() + '\n', 'table-definition.md': render_definition(found).rstrip() + '\n'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='서비스 DB 표 정의서 · ERD 생성')
    parser.add_argument('--out-dir', type=Path, default=OUT_DIR, help='출력 폴더(기본 db/schema)')
    parser.add_argument('--check', action='store_true', help='쓰지 않고 이미 있는 문서가 DB와 같은지만 본다')
    args = parser.parse_args(argv)
    url = os.getenv('DATABASE_URL')
    if not url:
        parser.error('DATABASE_URL이 필요합니다')
    with psycopg.connect(url) as conn:
        docs = generate(conn)
    stale = [name for name, text in docs.items() if not (args.out_dir / name).exists() or (args.out_dir / name).read_text(encoding='utf-8') != text]
    if args.check:
        print('DB와 다른 문서: ' + (', '.join(stale) if stale else '없음'))
        return 1 if stale else 0
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in docs.items():
        (args.out_dir / name).write_text(text, encoding='utf-8')
    print('썼음: ' + ', '.join(str(args.out_dir / name) for name in docs))
    return 0


if __name__ == '__main__':
    sys.exit(main())
