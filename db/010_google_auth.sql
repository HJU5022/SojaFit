-- Google 관리자 인증: 비밀번호 로그인과 기존 사용자 테이블은 변경하지 않는다.
CREATE TABLE auth_google_states (
    state_hash text PRIMARY KEY,
    browser_hash text NOT NULL,
    verifier text NOT NULL,
    nonce text NOT NULL,
    expires_at timestamptz NOT NULL
);

CREATE TABLE auth_google_pending (
    request_id text PRIMARY KEY,
    issuer text NOT NULL,
    subject text NOT NULL,
    email text NOT NULL,
    expires_at timestamptz NOT NULL
);

CREATE TABLE auth_google_identities (
    issuer text NOT NULL,
    subject text NOT NULL,
    user_id bigint NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (issuer, subject)
);

ALTER TABLE auth_google_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth_google_pending ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth_google_identities ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON auth_google_states, auth_google_pending, auth_google_identities FROM PUBLIC;
DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON auth_google_states, auth_google_pending, auth_google_identities FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
