"""서비스 표의 구조를 정규화해 출력한다(칸 · 제약 · 인덱스 · 트리거 · 함수). 두 DB를 비교하려고 같은 형식으로 뽑는다. 사용: rd_struct.py <port> <dbname>"""
import sys
import psycopg
port, dbname = sys.argv[1], sys.argv[2]
SERVICE = {"public": ["users","auth_sessions","auth_login_attempts","auth_login_ip_attempts","auth_signup_attempts","auth_google_states","auth_google_pending","auth_google_identities","projects","circuits","threads","runs","messages","approvals","quotes","approved_cases","app_migrations"],
           "sojafit_agent": ["circuits","threads","messages","approvals","analysis_events","analysis_usage","analysis_service_usage"]}
with psycopg.connect(f"postgresql://app:app@127.0.0.1:{port}/{dbname}") as c:
    for schema, tables in SERVICE.items():
        for t in tables:
            oid = c.execute("SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=%s AND c.relkind='r'", (schema, t)).fetchone()
            if not oid: continue
            oid = oid[0]
            for r in c.execute("SELECT a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull, COALESCE(pg_get_expr(d.adbin,d.adrelid),'') FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1", (oid,)):
                print(f"COL  {schema}.{t}.{r[0]} {r[1]} {'NN' if r[2] else 'N'} {r[3]}")
            for r in c.execute("SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s ORDER BY conname", (oid,)):
                print(f"CON  {schema}.{t} {r[0]} {r[1]} {' '.join(r[2].split())}")
            for r in c.execute("SELECT i.relname, pg_get_indexdef(i.oid) FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid WHERE x.indrelid=%s ORDER BY 1", (oid,)):
                print(f"IDX  {schema}.{t} {r[0]} {' '.join(r[1].split()).split(' USING ')[-1]}")
            for r in c.execute("SELECT tgname FROM pg_trigger WHERE tgrelid=%s AND NOT tgisinternal ORDER BY 1", (oid,)):
                print(f"TRG  {schema}.{t} {r[0]}")
            rls = c.execute("SELECT relrowsecurity FROM pg_class WHERE oid=%s", (oid,)).fetchone()[0]
            print(f"RLS  {schema}.{t} {'ON' if rls else 'OFF'}")
    for r in c.execute("SELECT n.nspname||'.'||p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('public','sojafit_agent') AND p.prokind='f' AND p.proname NOT IN ('rls_auto_enable') AND p.proname !~ '^(vector|halfvec|sparsevec|bit|l2|l1|cosine|inner|hamming|jaccard|ivfflat|hnsw|array_to|binary_quantize|subvector)' ORDER BY 1"):
        print(f"FUN  {r[0]}")
    # [왜] 함수 이름만 비교하면 되돌리기가 다시 만든 함수가 026이 회수한 PUBLIC 실행 권한을 되살려도 못 잡는다
    for r in c.execute("SELECT n.nspname||'.'||p.proname, COALESCE(p.proacl::text, 'default') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('public','sojafit_agent') AND p.proname IN ('conversation_json_matches','quote_snapshot_has_forbidden_key','purge_thread_checkpoints','purge_inactive_projects','purge_log_records') ORDER BY 1"):
        print(f"FACL {r[0]} {r[1]}")
