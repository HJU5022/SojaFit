-- 데모 프로젝트 허용 목록에 c01 회로(attiny85_time_switch)를 더한다. 키 없는 데모의 판정 질문 v3-01이 이 회로를 쓴다(11-10).
-- 빈 볼륨은 018이 이미 새 목록으로 만들고, 이 파일은 018을 먼저 적용한 기존 DB(운영 Supabase · 조원 로컬 볼륨)용이다. 여러 번 돌려도 결과가 같다.
-- 허용 목록은 backend/projects/repository.py의 DEMOS와 같아야 한다(tests/projects/test_project_repository.py가 대조).
ALTER TABLE projects DROP CONSTRAINT IF EXISTS ck_projects_demo;
ALTER TABLE projects ADD CONSTRAINT ck_projects_demo CHECK (
    (source_kind = 'demo' AND demo_id IS NOT NULL AND demo_id IN (
        'breadboard_supply', 'mosfet_driver', 'attiny85_dev', 'pro_micro', 'franzininho_diy', 'attiny85_time_switch'
    )) OR (source_kind = 'upload' AND demo_id IS NULL)
);
