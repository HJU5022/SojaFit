-- 실행 전 점검 4/4: migrate_prod_2b_optional_drop_dead_auth.sql 직전(승인 대기 코드를 지운 배포 뒤). 읽기 전용, 개수만 출력(이메일 같은 값은 찍지 않는다).
-- 사용: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -At -f db/migrations/precheck_4_before_2b.sql
BEGIN READ ONLY;
SELECT '[1] 이력 표 기대: 2026-11-expand, contract-p1, contract-p2 포함 = ' || (SELECT COALESCE(string_agg(version, ', ' ORDER BY applied_at), '(없음)') FROM public.app_migrations);
-- [왜] 표가 이미 없어도 이 질의가 오류 없이 돌도록 표 이름을 글자로 넘긴다
SELECT '[2] auth_google_pending 행(0이 아니면 확인 변수 app.ack_drop_google_pending 필요) = ' || CASE WHEN to_regclass('public.auth_google_pending') IS NULL THEN '(표 없음: 이미 삭제됨)'
    ELSE (xpath('/row/c/text()', query_to_xml('select count(*) as c from public.auth_google_pending', false, true, '')))[1]::text END;
ROLLBACK;
