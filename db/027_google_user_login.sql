-- Google 일반 계정은 비밀번호를 저장하지 않는다. 기존 해시·역할·Google 연결은 유지한다.
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='users'::regclass AND conname='users_admin_password_required') THEN
        ALTER TABLE users ADD CONSTRAINT users_admin_password_required CHECK (password_hash IS NOT NULL OR role='user');
    END IF;
END $$;
