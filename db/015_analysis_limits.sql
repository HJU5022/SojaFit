-- UTC 일자별 사용자 분석 예약액과 입장 빈도. 실제 청구액이 아니며 실패 시 환불하지 않는다.
CREATE TABLE IF NOT EXISTS sojafit_agent.analysis_usage (
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    day DATE NOT NULL,
    reserved_usd NUMERIC(16,10) NOT NULL DEFAULT 0 CHECK (reserved_usd >= 0),
    attempts INTEGER NOT NULL DEFAULT 1,
    next_allowed TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, day)
);
REVOKE ALL ON sojafit_agent.analysis_usage FROM PUBLIC;
DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
        REVOKE ALL ON sojafit_agent.analysis_usage FROM anon;
    END IF;
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
        REVOKE ALL ON sojafit_agent.analysis_usage FROM authenticated;
    END IF;
END $$;
