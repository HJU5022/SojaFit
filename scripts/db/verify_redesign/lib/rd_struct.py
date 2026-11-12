"""public · sojafit_agent의 모든 표 구조를 정규화해 출력한다(칸 · identity · 제약 · 인덱스 · 트리거 · RLS · 함수 본문 해시 · 함수 설정 · 함수 권한). 두 DB를 같은 형식으로 뽑아 diff 한다.
사용: rd_struct.py <port> <dbname>

- [왜] 예전에는 서비스 표 목록만 보고 함수는 이름만 찍어서, 함수 본문 · identity 종류 · 코퍼스 표 인덱스가 바뀌어도 비교가 0줄이었다(기준선에 변이를 넣어 확인).
- [주의] 확장이 만든 함수(pgvector)는 제외한다. 본문은 공백을 접은 뒤 md5로 줄여 찍는다(본문 한 글자만 달라도 줄이 달라진다).
"""
import sys
import psycopg
port, dbname = sys.argv[1], sys.argv[2]
SCHEMAS = ("public", "sojafit_agent")
with psycopg.connect(f"postgresql://app:app@127.0.0.1:{port}/{dbname}") as c:
    tables = c.execute("SELECT n.nspname, c.relname, c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname = ANY(%s) AND c.relkind='r' ORDER BY 1,2", (list(SCHEMAS),)).fetchall()
    for schema, t, oid in tables:
        for r in c.execute("SELECT a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull, COALESCE(pg_get_expr(d.adbin,d.adrelid),''), a.attidentity, a.attgenerated FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1", (oid,)):
            ident = {"a": "IDENTITY-ALWAYS", "d": "IDENTITY-DEFAULT"}.get(r[4], "")
            print(f"COL  {schema}.{t}.{r[0]} {r[1]} {'NN' if r[2] else 'N'} {r[3]} {ident} {'GEN-' + r[5] if r[5] else ''}".rstrip())
        for r in c.execute("SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s ORDER BY conname", (oid,)):
            print(f"CON  {schema}.{t} {r[0]} {r[1]} {' '.join(r[2].split())}")
        for r in c.execute("SELECT i.relname, pg_get_indexdef(i.oid) FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid WHERE x.indrelid=%s ORDER BY 1", (oid,)):
            print(f"IDX  {schema}.{t} {r[0]} {' '.join(r[1].split()).split(' USING ')[-1]}")
        for r in c.execute("SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger WHERE tgrelid=%s AND NOT tgisinternal ORDER BY 1", (oid,)):
            print(f"TRG  {schema}.{t} {r[0]} {' '.join(r[1].split()).split(' ON ')[-1]}")
        rls = c.execute("SELECT relrowsecurity FROM pg_class WHERE oid=%s", (oid,)).fetchone()[0]
        print(f"RLS  {schema}.{t} {'ON' if rls else 'OFF'}")
    for r in c.execute("""SELECT n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||')', md5(regexp_replace(p.prosrc, '\\s+', ' ', 'g')),
                                 p.prokind, p.provolatile, p.proisstrict, pg_get_function_result(p.oid), COALESCE(p.proconfig::text, ''), COALESCE(p.proacl::text, 'default')
                          FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                          WHERE n.nspname = ANY(%s) AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=p.oid AND d.deptype='e') ORDER BY 1""", (list(SCHEMAS),)):
        print(f"FUN  {r[0]} body={r[1]} {r[2]}{r[3]}{'S' if r[4] else ''} -> {r[5]}")
        print(f"FCFG {r[0]} {r[6]}")
        print(f"FACL {r[0]} {r[7]}")
