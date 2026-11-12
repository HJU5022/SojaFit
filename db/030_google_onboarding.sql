-- 새 기준선에서 명시적 Google 가입·기존 계정 재확인과 관리자 최초 승인을 지원한다.
-- 기존 사용자·신원 연결·세션을 바꾸지 않는다. 이전 DB는 배포 전 적용을 별도 검토한다.
CREATE TABLE IF NOT EXISTS auth_google_pending (
    request_id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    email TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
ALTER TABLE auth_google_pending ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON auth_google_pending FROM PUBLIC;
DO $$
DECLARE target TEXT;
BEGIN
    FOREACH target IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = target) THEN
            EXECUTE format('REVOKE ALL ON auth_google_pending FROM %I', target);
        END IF;
    END LOOP;
END $$;
