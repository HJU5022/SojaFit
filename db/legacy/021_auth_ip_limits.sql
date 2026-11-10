-- 클라이언트 IP 한도(backend/auth.py). IP 원문은 저장하지 않고 키 해시(ip_hash)만 둔다.
-- auth_signup_attempts: IP별 UTC 하루 가입 요청 수(signup). auth_login_ip_attempts: IP별 15분 로그인 실패 수와 잠금(authenticate).
-- 새 볼륨 첫 기동 때 자동 실행된다(003 다음). 다시 실행해도 아무것도 바꾸지 않으며, 기존 DB에는 따로 적용한다.
CREATE TABLE IF NOT EXISTS auth_signup_attempts (
    ip_hash CHAR(64) NOT NULL,
    day DATE NOT NULL,
    signup_count INTEGER NOT NULL DEFAULT 1 CHECK (signup_count >= 1),
    PRIMARY KEY (ip_hash, day)
);

-- 열의 뜻은 auth_login_attempts(003·005)와 같다: 실패 횟수, 15분 집계 창 시작 시각, 잠금 끝 시각
CREATE TABLE IF NOT EXISTS auth_login_ip_attempts (
    ip_hash CHAR(64) PRIMARY KEY,
    failed_count INTEGER NOT NULL DEFAULT 0,
    window_started_at TIMESTAMPTZ,
    locked_until TIMESTAMPTZ
);

ALTER TABLE auth_signup_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth_login_ip_attempts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON auth_signup_attempts, auth_login_ip_attempts FROM PUBLIC;
DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON auth_signup_attempts, auth_login_ip_attempts FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
