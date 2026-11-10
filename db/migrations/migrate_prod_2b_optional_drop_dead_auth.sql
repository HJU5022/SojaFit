-- 선택 이전(2b): 승인 대기 흐름의 코드를 지운 **뒤에만** 실행한다. 운영에는 아직 실행하지 않았다.
-- 전제: backend/auth.py의 request_google_link · approve_google_link · google_pending_email, backend/api/auth.py의 /google/pending, CLI --approve-google을
--       지운 코드가 배포됐다(11-10 구글 자동 연결 결정으로 콜백이 더 이상 부르지 않는다). 되돌리기는 migrate_prod_4_rollback.sql의 B2b 절(빈 표를 RLS ON으로 다시 만든다).
-- 데이터 손실 가드: 승인 대기 표에는 이메일 평문이 든 행이 있을 수 있다. 행이 있으면 명시 확인 없이는 중단한다:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SET app.ack_drop_google_pending='yes'" -f db/migrations/migrate_prod_2b_optional_drop_dead_auth.sql
BEGIN;
DO $$
DECLARE n bigint;
BEGIN
    SELECT count(*) INTO n FROM public.auth_google_pending;
    RAISE NOTICE '[점검] auth_google_pending 행: % (이 표는 삭제된다)', n;
    IF n > 0 AND COALESCE(current_setting('app.ack_drop_google_pending', true), '') <> 'yes' THEN
        RAISE EXCEPTION 'auth_google_pending에 %행이 있다(이메일 평문). 지워도 되면 SET app.ack_drop_google_pending=''yes'' 를 같은 세션에서 먼저 실행하라', n;
    END IF;
END $$;
DROP TABLE public.auth_google_pending;
INSERT INTO public.app_migrations (version, note) VALUES ('2026-11-drop-google-pending', '승인 대기 표 제거');
COMMIT;
