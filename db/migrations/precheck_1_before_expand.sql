-- 실행 전 점검 1/3: migrate_prod_1_expand.sql 직전. **읽기 전용**이고 개수(와 id)만 출력한다(질문 · 답 · 이메일 같은 내용은 찍지 않는다). 모든 값이 "기대"와 같아야 expand를 실행한다.
-- 사용: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -At -f db/migrations/precheck_1_before_expand.sql
BEGIN READ ONLY;
SELECT '[1] 백업이 필요한 표 수(기대: public 서비스 표 16 + sojafit_agent 표) = ' || count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname IN ('public', 'sojafit_agent') AND c.relkind = 'r';
SELECT '[2] users.display_name 값이 있는 행(P1에서 칸이 삭제된다. 0이 아니면 P1에 확인 변수가 필요) = ' || count(display_name) FROM public.users;
SELECT '[3] sojafit_agent.threads 고아(같은 UUID의 public.threads 없음. 기대 0) = ' || count(*) FROM sojafit_agent.threads t WHERE NOT EXISTS (SELECT 1 FROM public.threads p WHERE p.id = t.id);
SELECT '[4] 승인 snapshot에 candidate.part · verdict 없음(기대 0) = ' || count(*) FROM public.approvals WHERE snapshot #>> '{candidate,part}' IS NULL OR snapshot #>> '{candidate,verdict}' IS NULL;
SELECT '[5] 승인 candidate.part가 1~100자 아님(기대 0) = ' || count(*) FROM public.approvals WHERE char_length(snapshot #>> '{candidate,part}') NOT BETWEEN 1 AND 100;
SELECT '[6] 승인 verdict가 허용 3값 아님(기대 0) = ' || count(*) FROM public.approvals WHERE snapshot #>> '{candidate,verdict}' NOT IN ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT');
SELECT '[7] 승인 품번이 형식에 안 맞음(기대 0) = ' || count(*) FROM public.approvals WHERE COALESCE(snapshot #>> '{candidate,part_number}',
    regexp_replace(regexp_replace(btrim(snapshot #>> '{candidate,part}'), '^\s*(TSC|Taiwan\s+Semiconductor)\s+', '', 'i'), '\s+', '-', 'g')) !~ '^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$';
SELECT '[8] 프로젝트가 새 검사(데모일 때만 demo_id)에 안 맞음(기대 0) = ' || count(*) FROM public.projects WHERE (source_kind = 'demo') <> (demo_id IS NOT NULL);
SELECT '[9] runs.safe_result가 필수 키 6개 검사에 안 맞음(기대 0) = ' || count(*) FROM public.runs WHERE safe_result IS NOT NULL
    AND NOT (jsonb_typeof(safe_result) = 'object' AND safe_result ?& ARRAY['answer', 'question_type', 'price_parts', 'interrupt', 'judgement', 'evidence']);
SELECT '[10] 체크포인트 고아 = 화면 대화(public.threads)에 없는 thread_id (checkpoints / blobs / writes, 이전 뒤에는 트리거가 새 고아를 막는다. 참고용) = '
    || (SELECT count(DISTINCT thread_id) FROM sojafit_agent.checkpoints c WHERE NOT EXISTS (SELECT 1 FROM public.threads t WHERE t.id::text = c.thread_id)) || ' / '
    || (SELECT count(DISTINCT thread_id) FROM sojafit_agent.checkpoint_blobs c WHERE NOT EXISTS (SELECT 1 FROM public.threads t WHERE t.id::text = c.thread_id)) || ' / '
    || (SELECT count(DISTINCT thread_id) FROM sojafit_agent.checkpoint_writes c WHERE NOT EXISTS (SELECT 1 FROM public.threads t WHERE t.id::text = c.thread_id));
SELECT '[11] 이력 표 app_migrations(기대: 아직 없음 = f) = ' || (to_regclass('public.app_migrations') IS NOT NULL);
ROLLBACK;
