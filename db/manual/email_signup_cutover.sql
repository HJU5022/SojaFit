-- 029와 새 인증 코드를 검증한 뒤 운영 전환 시 한 번 적용한다.
-- 기존 행을 갱신하지 않고 구버전 공개 주소의 무인증 신규 INSERT를 차단한다.
DO $$
BEGIN
    LOCK TABLE public.users IN ACCESS EXCLUSIVE MODE;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.users'::regclass AND conname = 'users_email_signup_cutover'
    ) THEN
        EXECUTE format(
            'ALTER TABLE public.users ADD CONSTRAINT users_email_signup_cutover CHECK (created_at < %L::timestamptz OR email_verified_at IS NOT NULL)',
            clock_timestamp()
        );
    END IF;
END $$;
