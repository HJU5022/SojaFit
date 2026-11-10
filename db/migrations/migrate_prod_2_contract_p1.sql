-- 운영 DB 이전 2단계 "contract P1"(축소 1): **되돌릴 수 없는 삭제**가 들어 있다. 초안, 아직 어디에도 실행하지 않았다.
--
-- 전제(하나라도 아니면 실행하지 않는다):
--   ① migrate_prod_1_expand.sql을 적용했다
--   ② **P1 새 코드가 배포돼 100%이고** 스모크 28단계가 통과했다. P1 새 코드 = backend/services/quote.py가 approvals의 candidate_part · verdict · part_number 칸을 쓰고,
--      quotes · approved_cases에 snapshot을 쓰지도 읽지도 않으며(승인 사례 목록은 approvals를 JOIN), users.display_name을 참조하지 않는다.
--   ③ 실행 직전 백업을 받았다(1단계 파일 머리 참고).
-- 하는 일: 승인 칸 NOT NULL, 스냅샷 복사본 2개 제거, 앱 JSON 모양을 복제하던 검사를 단순 검사로 교체, 미사용 칸 제거.
-- 분석 서비스(sojafit_agent) 쪽 정리는 코드 변경이 커서 migrate_prod_3_contract_p2.sql로 따로 둔다(P1만 먼저 끝낼 수 있다).
-- 되돌리기: migrate_prod_4_rollback.sql의 B1 절(지운 것은 모두 다른 표의 복사본이거나 미사용이라 무손실).
-- 데이터 손실 가드: 아래 삭제가 버리는 값이 있으면 **명시 확인 없이는 중단**한다. 확인이 필요하면 같은 psql 세션에서 먼저 SET 한다:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SET app.ack_drop_display_name='yes'" -f db/migrations/migrate_prod_2_contract_p1.sql
BEGIN;

-- G1. 사전 점검(삭제 전). 사전 점검 수치는 NOTICE로 찍힌다
DO $$
DECLARE n bigint; named bigint; cases bigint;
BEGIN
    SELECT count(display_name) INTO named FROM public.users;
    RAISE NOTICE '[점검] users.display_name 값이 있는 행: % (이 칸은 삭제된다)', named;
    IF named > 0 AND COALESCE(current_setting('app.ack_drop_display_name', true), '') <> 'yes' THEN
        RAISE EXCEPTION 'users.display_name에 값이 있는 행이 %개다. 지워도 되는지 확인한 뒤 SET app.ack_drop_display_name=''yes'' 를 같은 세션에서 먼저 실행하라', named;
    END IF;
    -- quotes · approved_cases의 snapshot은 approvals.snapshot과 같다는 가정이 삭제의 근거다. NULL(새 코드가 안 채움)은 허용, 값이 있는데 다르면 중단
    SELECT count(*) INTO n FROM public.quotes q JOIN public.approvals a ON a.id = q.approval_id
        WHERE q.snapshot IS NOT NULL AND q.snapshot IS DISTINCT FROM a.snapshot;
    RAISE NOTICE '[점검] quotes.snapshot이 approvals.snapshot과 다른 행: %', n;
    IF n > 0 THEN RAISE EXCEPTION 'quotes.snapshot % 행이 approvals.snapshot과 다르다: 복사본이 아니므로 지우면 정보가 사라진다', n; END IF;
    SELECT count(*) INTO cases FROM public.approved_cases c JOIN public.approvals a ON a.id = c.approval_id
        WHERE c.snapshot IS NOT NULL AND c.snapshot IS DISTINCT FROM a.snapshot;
    RAISE NOTICE '[점검] approved_cases.snapshot이 approvals.snapshot과 다른 행: %', cases;
    IF cases > 0 THEN RAISE EXCEPTION 'approved_cases.snapshot % 행이 approvals.snapshot과 다르다: 복사본이 아니므로 지우면 정보가 사라진다', cases; END IF;
END $$;

-- C0. 옛 코드가 expand 뒤 배포 전까지 넣은 승인 행(새 칸 NULL)을 채우고 NOT NULL로 만든다
UPDATE public.approvals SET
    candidate_part = COALESCE(candidate_part, snapshot #>> '{candidate,part}'),
    verdict        = COALESCE(verdict, snapshot #>> '{candidate,verdict}'),
    part_number    = COALESCE(part_number, snapshot #>> '{candidate,part_number}',
                              regexp_replace(regexp_replace(btrim(snapshot #>> '{candidate,part}'), '^\s*(TSC|Taiwan\s+Semiconductor)\s+', '', 'i'), '\s+', '-', 'g'))
WHERE candidate_part IS NULL OR verdict IS NULL OR part_number IS NULL;
ALTER TABLE public.approvals ALTER COLUMN candidate_part SET NOT NULL, ALTER COLUMN verdict SET NOT NULL, ALTER COLUMN part_number SET NOT NULL;

-- C1. 승인 스냅샷 복사본 제거(견적은 아무도 읽지 않았고, 승인 사례는 이제 approvals를 JOIN해서 읽는다)
ALTER TABLE public.quotes DROP COLUMN snapshot;
ALTER TABLE public.approved_cases DROP COLUMN snapshot;

-- C2. 앱 JSON 모양을 복제하던 검사를 단순 검사로 교체
ALTER TABLE public.runs DROP CONSTRAINT runs_safe_result_check;
ALTER TABLE public.runs RENAME CONSTRAINT ck_runs_safe_result_v2 TO ck_runs_safe_result;
DROP FUNCTION public.conversation_json_matches(jsonb, jsonb);
ALTER TABLE public.projects DROP CONSTRAINT ck_projects_demo;
ALTER TABLE public.projects RENAME CONSTRAINT ck_projects_demo_v2 TO ck_projects_demo;

-- C3. 쓰지 않는 칸
ALTER TABLE public.users DROP COLUMN display_name;

INSERT INTO public.app_migrations (version, note) VALUES ('2026-11-contract-p1', 'migrate_prod_2_contract_p1.sql: 승인 칸 NOT NULL, 스냅샷 복사본 · 미사용 칸 제거, 단순 검사로 교체');
COMMIT;
