-- 내용 없이 요청·분석·단계 지연만 남기는 운영 기록. 사람의 조건 입력 대기는 실행 시간에서 제외한다.
CREATE TABLE IF NOT EXISTS sojafit_agent.analysis_events (
    id UUID PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES sojafit_agent.threads(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    request_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    elapsed_ms INTEGER NOT NULL,
    stages JSONB NOT NULL,
    trace_id TEXT NOT NULL,
    trace_delivery TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS agent_events_thread ON sojafit_agent.analysis_events(thread_id,created_at DESC);
REVOKE ALL ON sojafit_agent.analysis_events FROM PUBLIC;
DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
        REVOKE ALL ON sojafit_agent.analysis_events FROM anon;
    END IF;
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
        REVOKE ALL ON sojafit_agent.analysis_events FROM authenticated;
    END IF;
END $$;
