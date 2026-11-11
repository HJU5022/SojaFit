-- 회로 카탈로그가 데이터 파일로 확장되므로 데모 id를 DB CHECK에 고정하지 않는다.
-- source_kind/demo_id의 관계(데모는 id 필수, 업로드는 id 없음)는 유지한다.
ALTER TABLE projects DROP CONSTRAINT IF EXISTS ck_projects_demo;
ALTER TABLE projects ADD CONSTRAINT ck_projects_demo CHECK (
    (source_kind = 'demo' AND demo_id IS NOT NULL AND btrim(demo_id) <> '')
    OR (source_kind = 'upload' AND demo_id IS NULL)
);
