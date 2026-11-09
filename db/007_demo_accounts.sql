-- 로컬 Compose 데모 계정 시드. 새 PostgreSQL 볼륨 초기화 때만 실행됩니다(11-09 결정).
-- DEMO_MODE=1이면 로컬 데모 전용 일반 사용자 2개(demo-a · demo-b)를 만듭니다. 평가용으로 제출한 계정과 다른 계정입니다.
-- 비밀번호가 없습니다: password_hash는 scrypt 형식이 아닌 표식이라 비밀번호 로그인은 늘 실패하고,
-- 로그인 화면의 "데모 사용자 A · B로 들어가기" 버튼(POST /api/auth/demo-login, 데모 모드에서만 있음)으로만 들어갑니다.
-- [주의] 표식은 backend/auth.py의 DEMO_PASSWORD_HASH와 같아야 한다. 버튼 로그인은 이 표식을 가진 일반 계정에만 세션을 준다.
-- 저장소에 비밀번호 · 해시를 두지 않습니다. 그 밖의 계정은 /signup 가입이나 `python -m backend.auth`로 만듭니다.
\getenv demo_mode DEMO_MODE
\if :{?demo_mode}
\else
\set demo_mode ''
\endif

SELECT set_config('sojafit.demo_mode', :'demo_mode', false) AS demo_mode
\gset

DO $$
BEGIN
    IF current_setting('sojafit.demo_mode', true) IS DISTINCT FROM '1' THEN
        RAISE NOTICE 'Demo accounts skipped because DEMO_MODE is not 1.';
        RETURN;
    END IF;
    INSERT INTO users (login_id, password_hash, role)
    VALUES ('demo-a@example.test', 'demo-button-login-only', 'user'),
           ('demo-b@example.test', 'demo-button-login-only', 'user')
    ON CONFLICT (login_id) DO NOTHING;
END
$$;
