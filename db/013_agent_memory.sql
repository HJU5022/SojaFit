-- 사용자 업로드·분석 thread 메타데이터. LangGraph 내부 표는 setup CLI가 생성한다.
CREATE SCHEMA IF NOT EXISTS sojafit_agent;
REVOKE ALL ON SCHEMA sojafit_agent FROM PUBLIC;
CREATE TABLE IF NOT EXISTS sojafit_agent.circuits (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    filename TEXT NOT NULL,
    netlist TEXT NOT NULL,
    connections JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sojafit_agent.threads (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    circuit_id UUID NOT NULL REFERENCES sojafit_agent.circuits(id) ON DELETE RESTRICT,
    target TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    retries INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'NEW' CHECK(status IN ('NEW','RUNNING','WAITING','DONE','FAILED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS agent_threads_owner ON sojafit_agent.threads(user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS agent_circuits_owner ON sojafit_agent.circuits(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS sojafit_agent.messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES sojafit_agent.threads(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    checkpoint_id TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS agent_messages_thread ON sojafit_agent.messages(thread_id,id);
ALTER TABLE sojafit_agent.threads ADD COLUMN IF NOT EXISTS retries INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sojafit_agent.messages ADD COLUMN IF NOT EXISTS checkpoint_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS agent_messages_checkpoint ON sojafit_agent.messages(thread_id,checkpoint_id) WHERE checkpoint_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS sojafit_agent.approvals (
    thread_id UUID NOT NULL REFERENCES sojafit_agent.threads(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(thread_id,version)
);
REVOKE ALL ON ALL TABLES IN SCHEMA sojafit_agent FROM PUBLIC;
DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
        REVOKE ALL ON SCHEMA sojafit_agent FROM anon;
        REVOKE ALL ON ALL TABLES IN SCHEMA sojafit_agent FROM anon;
    END IF;
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
        REVOKE ALL ON SCHEMA sojafit_agent FROM authenticated;
        REVOKE ALL ON ALL TABLES IN SCHEMA sojafit_agent FROM authenticated;
    END IF;
END $$;
