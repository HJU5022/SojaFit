-- 로컬 Compose 데모 계정 시드. 새 PostgreSQL 볼륨 초기화 때만 실행됩니다.
-- 기본 데모 계정은 DEMO_MODE=1이고 네 변수가 모두 비어 있을 때 생성됩니다. 재정의하려면 네 값을 모두 설정하세요.
-- 각 계정의 해시는 `uv run python -m backend.auth --hash-only`를 실행하고
-- 최소 12자 비밀번호를 두 번 입력해 생성합니다. 평문 비밀번호는 .env에 넣지 마세요.
-- scrypt 해시에 `$`가 포함되므로 .env의 해시 값은 작은따옴표로 감싸세요.
-- DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD_HASH, DEMO_USER_EMAIL, DEMO_USER_PASSWORD_HASH
-- 실서비스 및 제출용 계정 정보는 저장소에 넣지 마세요. 이 시드는 로컬 Compose 전용입니다.
\getenv demo_mode DEMO_MODE
\if :{?demo_mode}
\else
\set demo_mode ''
\endif
\getenv demo_admin_email DEMO_ADMIN_EMAIL
\getenv demo_admin_password_hash DEMO_ADMIN_PASSWORD_HASH
\getenv demo_user_email DEMO_USER_EMAIL
\getenv demo_user_password_hash DEMO_USER_PASSWORD_HASH

SELECT set_config('sojafit.demo_mode', :'demo_mode', false) AS demo_mode,
       set_config('sojafit.demo_admin_email', :'demo_admin_email', false) AS admin_email,
       set_config('sojafit.demo_admin_password_hash', :'demo_admin_password_hash', false) AS admin_hash,
       set_config('sojafit.demo_user_email', :'demo_user_email', false) AS user_email,
       set_config('sojafit.demo_user_password_hash', :'demo_user_password_hash', false) AS user_hash
\gset

DO $$
DECLARE
    admin_email TEXT := current_setting('sojafit.demo_admin_email');
    admin_hash TEXT := current_setting('sojafit.demo_admin_password_hash');
    user_email TEXT := current_setting('sojafit.demo_user_email');
    user_hash TEXT := current_setting('sojafit.demo_user_password_hash');
BEGIN
    IF admin_email = '' AND admin_hash = '' AND user_email = '' AND user_hash = '' THEN
        IF current_setting('sojafit.demo_mode', true) IS DISTINCT FROM '1' THEN
            RAISE NOTICE 'Demo defaults skipped because DEMO_MODE is not 1.';
            RETURN;
        END IF;
        admin_email := 'demo-admin@example.test';
        admin_hash := 'scrypt$01010101010101010101010101010101$3065811962eecf2a96fb61016ded65bb5bea92e2dd142a76ecf2ecd024dc6b51';
        user_email := 'demo-user@example.test';
        user_hash := 'scrypt$02020202020202020202020202020202$82f3e703404f15d81c0e0d05064ae1728395453f8d84cd0087f3f06baca06b92';
    END IF;

    IF admin_email = '' OR user_email = ''
       OR length(admin_email) > 100 OR length(user_email) > 100
       OR admin_email !~ '^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$'
       OR user_email !~ '^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$'
       OR lower(admin_email) = lower(user_email)
       OR admin_hash !~ '^scrypt\$[0-9a-f]{32}\$[0-9a-f]{64}$'
       OR user_hash !~ '^scrypt\$[0-9a-f]{32}\$[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Demo account configuration is incomplete or invalid; check .env values.';
    END IF;

    INSERT INTO users (login_id, password_hash, role)
    VALUES (lower(admin_email), admin_hash, 'admin'),
           (lower(user_email), user_hash, 'user')
    ON CONFLICT (login_id) DO NOTHING;
END
$$;
