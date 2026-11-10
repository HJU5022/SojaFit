-- 현재 결과 버전의 사용자 원문·명시 조건·재개 답변. 과거 값은 추측해 채우지 않는다.
ALTER TABLE sojafit_agent.threads ADD COLUMN IF NOT EXISTS input_record JSONB;
