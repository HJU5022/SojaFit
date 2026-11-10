-- 선택 이전(2b): 승인 대기 흐름의 코드를 지운 **뒤에만** 실행한다. 운영에는 아직 실행하지 않았다.
-- 전제: backend/auth.py의 request_google_link · approve_google_link · google_pending_email, backend/api/auth.py의 /google/pending, CLI --approve-google을
--       지운 코드가 배포됐다(11-10 구글 자동 연결 결정으로 콜백이 더 이상 부르지 않는다). 되돌리기는 migrate_prod_4_rollback.sql의 B2b 절(빈 표를 RLS ON으로 다시 만든다).
BEGIN;
DROP TABLE public.auth_google_pending;
INSERT INTO public.app_migrations (version, note) VALUES ('2026-11-drop-google-pending', '승인 대기 표 제거');
COMMIT;
