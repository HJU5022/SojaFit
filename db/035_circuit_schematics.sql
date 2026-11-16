-- 새 DB 및 기존 서비스 DB용. 사용자가 올린 KiCad 회로도(.kicad_sch) 원문을 그 회로 버전에 붙여 두는 표 하나만 더한다(#52, SPEC 4절).
-- 그림(PNG)은 저장하지 않는다. 화면이 열 때 렌더러로 다시 그리고 API 메모리 캐시(15분)에만 둔다.
-- 행은 업로드와 같은 트랜잭션에서 INSERT만 한다. 프로젝트를 지우면 회로 버전과 함께 지워진다(FK CASCADE).
-- 재실행 가능(표가 있으면 건너뜀). 기존 DB에는 psql -1 -v ON_ERROR_STOP=1 -f db/035_circuit_schematics.sql로 적용한다.
-- 되돌리기: DROP TABLE IF EXISTS circuit_schematics; DELETE FROM app_migrations WHERE version='035-circuit-schematics'; (올린 회로도 원문이 사라지고 화면은 웹 검색으로 돌아간다)
CREATE TABLE IF NOT EXISTS circuit_schematics (
    project_id      BIGINT NOT NULL,
    circuit_version INTEGER NOT NULL CHECK (circuit_version >= 1),
    file_name       TEXT NOT NULL CHECK (char_length(btrim(file_name)) BETWEEN 1 AND 255),
    source          TEXT NOT NULL CHECK (octet_length(source) BETWEEN 1 AND 5242880),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, circuit_version),
    FOREIGN KEY (project_id, circuit_version) REFERENCES project_circuit_versions(project_id, version) ON DELETE CASCADE
);
ALTER TABLE circuit_schematics ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON circuit_schematics FROM PUBLIC;
DO $$ DECLARE role_name TEXT; BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('REVOKE ALL ON circuit_schematics FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
INSERT INTO app_migrations(version,note) VALUES ('035-circuit-schematics','Uploaded KiCad schematic source per circuit version') ON CONFLICT DO NOTHING;
