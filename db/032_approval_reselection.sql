-- 승인 snapshot/기존 견적은 보존하고, 활성 사례를 삭제한 메시지의 재승인을 허용한다.
-- 새 QuoteService(동일 run 잠금 + 활성 사례 검사)를 먼저 배포한 뒤 한 트랜잭션으로 적용한다.
ALTER TABLE approvals DROP CONSTRAINT IF EXISTS approvals_message_id_key;
CREATE INDEX IF NOT EXISTS ix_approvals_message ON approvals(message_id);
