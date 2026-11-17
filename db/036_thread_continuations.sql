-- 새 회로 버전으로 이어진 대화의 원래 thread 연결만 저장한다. 메시지·run·checkpoint는 복사하지 않는다.
CREATE TABLE IF NOT EXISTS thread_continuations (
    thread_id          UUID PRIMARY KEY REFERENCES threads(id) ON DELETE CASCADE,
    previous_thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    CONSTRAINT ck_thread_continuations_not_self CHECK (thread_id <> previous_thread_id)
);
CREATE INDEX IF NOT EXISTS ix_thread_continuations_previous ON thread_continuations(previous_thread_id);
ALTER TABLE thread_continuations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON thread_continuations FROM PUBLIC;
DO $$ DECLARE role_name TEXT; BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('REVOKE ALL ON thread_continuations FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
INSERT INTO app_migrations(version,note) VALUES ('036-thread-continuations','Link a new circuit thread to its previous conversation without copying messages') ON CONFLICT DO NOTHING;
