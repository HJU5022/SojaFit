-- 실행 전 점검 2/3: migrate_prod_2_contract_p1.sql 직전(expand와 P1 새 코드 배포 뒤). 읽기 전용, 개수만 출력.
-- 사용: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -At -f db/migrations/precheck_2_before_p1.sql
BEGIN READ ONLY;
SELECT '[1] 이력 표 기대: 2026-11-expand 포함 = ' || (SELECT COALESCE(string_agg(version, ', ' ORDER BY applied_at), '(없음)') FROM public.app_migrations);
SELECT '[2] users.display_name 값이 있는 행(0이 아니면 확인 변수 app.ack_drop_display_name 필요) = ' || count(display_name) FROM public.users;
SELECT '[3] quotes.snapshot이 approvals.snapshot과 다른 행(기대 0. NULL은 제외) = ' || count(*) FROM public.quotes q JOIN public.approvals a ON a.id = q.approval_id WHERE q.snapshot IS NOT NULL AND q.snapshot IS DISTINCT FROM a.snapshot;
SELECT '[4] approved_cases.snapshot이 approvals.snapshot과 다른 행(기대 0) = ' || count(*) FROM public.approved_cases c JOIN public.approvals a ON a.id = c.approval_id WHERE c.snapshot IS NOT NULL AND c.snapshot IS DISTINCT FROM a.snapshot;
SELECT '[5] 승인의 새 칸이 비어 있는 행(옛 코드가 expand 뒤에 넣은 행. P1이 채운다) = ' || count(*) FROM public.approvals WHERE candidate_part IS NULL OR verdict IS NULL OR part_number IS NULL;
SELECT '[6] expand가 만든 객체(기대 3행: FK, 새 검사 2) = ' || count(*) FROM pg_constraint WHERE conname IN ('fk_agent_threads_thread', 'ck_runs_safe_result_v2', 'ck_projects_demo_v2');
ROLLBACK;
