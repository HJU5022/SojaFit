-- 승인 원본을 수정하지 않고 향후 기억 참조 여부와 사용자 정정 메모를 관리한다.
ALTER TABLE sojafit_agent.approvals
    ADD COLUMN IF NOT EXISTS memory_status TEXT NOT NULL DEFAULT 'active'
    CHECK (memory_status IN ('active','revoked','deleted'));
ALTER TABLE sojafit_agent.approvals ADD COLUMN IF NOT EXISTS correction TEXT NOT NULL DEFAULT '';
ALTER TABLE sojafit_agent.approvals ADD COLUMN IF NOT EXISTS memory_updated_at TIMESTAMPTZ;
