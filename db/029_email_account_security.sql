-- 추가 전용: 기존 계정·비밀번호·역할·업무 자료는 변경하지 않는다.
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS public.auth_email_challenges (
    email VARCHAR(100) NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('signup', 'reset')),
    token_hash CHAR(64) NOT NULL UNIQUE,
    user_id BIGINT REFERENCES public.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (email, purpose),
    CHECK ((purpose = 'signup' AND user_id IS NULL) OR (purpose = 'reset' AND user_id IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS public.auth_email_send_limits (
    key_hash CHAR(64) PRIMARY KEY,
    window_start TIMESTAMPTZ NOT NULL,
    request_count INTEGER NOT NULL CHECK (request_count BETWEEN 1 AND 200)
);
ALTER TABLE public.auth_email_challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_email_send_limits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.auth_email_challenges, public.auth_email_send_limits FROM PUBLIC;
DO $$
DECLARE target TEXT;
BEGIN
    FOREACH target IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = target) THEN
            EXECUTE format('REVOKE ALL ON public.auth_email_challenges, public.auth_email_send_limits FROM %I', target);
        END IF;
    END LOOP;
END $$;
