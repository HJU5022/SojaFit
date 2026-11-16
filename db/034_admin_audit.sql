-- 새 DB 및 기존 서비스 DB용. 관리자가 계정에 한 일(가림 해제 · 정지 · 재활성화 · 탈퇴 처리)의 이력 표 하나만 더한다(SPEC 8.6).
-- 앱은 INSERT · SELECT만 하고 고치는 코드는 없다. 1년 지난 행은 새 분석 시작 때 지운다(memory_service._purge_expired, SPEC 8.5). 가림 해제는 원문을 돌려주기 전에 같은 트랜잭션에서 먼저 쓴다.
-- target_id에 FK를 두지 않는다: 탈퇴 처리로 계정 행이 지워져도 이력은 남아야 한다. 그래서 누구였는지는 가린 이메일로만 남긴다.
-- 재실행 가능(표가 있으면 건너뜀). 기존 DB에는 psql -1 -v ON_ERROR_STOP=1 -f db/034_admin_audit.sql로 적용한다.
-- 되돌리기: DROP TABLE IF EXISTS admin_audit; DELETE FROM app_migrations WHERE version='034-admin-audit'; (관리자 작업 이력이 사라진다)
CREATE TABLE IF NOT EXISTS admin_audit (
    id                  BIGSERIAL PRIMARY KEY,
    actor_id            BIGINT NOT NULL REFERENCES users(id),
    target_id           BIGINT NOT NULL,
    target_email_masked TEXT NOT NULL,
    action              TEXT NOT NULL CHECK (action IN ('unmask', 'deactivate', 'activate', 'delete')),
    fields              TEXT[] NOT NULL DEFAULT '{}' CHECK (fields <@ ARRAY['email']::TEXT[]),
    reason              TEXT CHECK (reason IS NULL OR char_length(reason) BETWEEN 5 AND 500),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (action <> 'unmask' OR (reason IS NOT NULL AND cardinality(fields) > 0))  -- 가림 해제는 사유와 연 칸이 반드시 있다
);
ALTER TABLE admin_audit ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON admin_audit FROM PUBLIC;
DO $$ DECLARE role_name TEXT; BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('REVOKE ALL ON admin_audit FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
INSERT INTO app_migrations(version,note) VALUES ('034-admin-audit','Append-only admin action history') ON CONFLICT DO NOTHING;
