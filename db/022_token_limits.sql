-- 하루 LLM 토큰 상한(사용자 200,000 · 서비스 전체 2,000,000, UTC 날짜, 11-09 결정)의 예약 토큰 카운터.
-- [주의] 공급자가 청구한 토큰 수가 아니다. 호출마다 USD 예약과 같은 위쪽 경계(입력 바이트 + 여유 8192 + 출력 상한)를 호출 전에 더하고,
--        실패한 호출도 돌려주지 않는다(backend/conversations/memory_service.py `_budget`).
-- 새 볼륨은 이름순으로 자동 실행되고(015 다음), 분석 준비 명령(memory_service --setup)이 다시 실행해도 아무것도 바꾸지 않는다.
ALTER TABLE sojafit_agent.analysis_usage ADD COLUMN IF NOT EXISTS reserved_tokens BIGINT NOT NULL DEFAULT 0 CHECK (reserved_tokens >= 0);
CREATE TABLE IF NOT EXISTS sojafit_agent.analysis_service_usage (
    day DATE PRIMARY KEY,
    reserved_tokens BIGINT NOT NULL DEFAULT 0 CHECK (reserved_tokens >= 0)
);
REVOKE ALL ON sojafit_agent.analysis_service_usage FROM PUBLIC;
DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
        REVOKE ALL ON sojafit_agent.analysis_service_usage FROM anon;
    END IF;
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
        REVOKE ALL ON sojafit_agent.analysis_service_usage FROM authenticated;
    END IF;
END $$;
