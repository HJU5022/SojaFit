-- Project ownership is enforced by repository queries; public API roles have no access.
CREATE TABLE threads (
    id UUID PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_threads_project ON threads(project_id);
CREATE TABLE runs (
    id UUID PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('running', 'requires_input', 'completed', 'refused', 'failed')),
    safe_result JSONB CHECK (safe_result IS NULL OR (jsonb_typeof(safe_result) = 'object' AND safe_result ? 'answer' AND jsonb_typeof(safe_result->'answer') = 'string' AND safe_result - 'answer' = '{}'::jsonb)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, thread_id)
);
CREATE INDEX ix_runs_thread ON runs(thread_id);
CREATE UNIQUE INDEX ix_runs_active ON runs(thread_id) WHERE status IN ('running', 'requires_input');
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    run_id UUID NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id, thread_id) REFERENCES runs(id, thread_id) ON DELETE CASCADE
);
CREATE INDEX ix_messages_thread ON messages(thread_id);
CREATE INDEX ix_messages_run ON messages(run_id);
ALTER TABLE threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON threads, runs, messages FROM PUBLIC;
REVOKE ALL ON SEQUENCE messages_id_seq FROM PUBLIC;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON threads, runs, messages FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON SEQUENCE messages_id_seq FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
