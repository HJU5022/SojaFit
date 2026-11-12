-- 사용자 소유 프로젝트와 정규화 회로. 기존 볼륨·공유 DB에는 자동 적용하지 않는다.
CREATE TABLE projects (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    demo_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_projects PRIMARY KEY (id),
    CONSTRAINT fk_projects_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_projects_name CHECK (name = btrim(name) AND char_length(name) BETWEEN 1 AND 200),
    CONSTRAINT ck_projects_source_kind CHECK (source_kind IN ('demo', 'upload')),
    CONSTRAINT ck_projects_demo CHECK (
        (source_kind = 'demo' AND demo_id IS NOT NULL AND demo_id IN (
            'breadboard_supply', 'mosfet_driver', 'attiny85_dev', 'pro_micro', 'franzininho_diy', 'attiny85_time_switch'
        )) OR (source_kind = 'upload' AND demo_id IS NULL)
    )
);
-- user_id 선두: 소유자별 목록 정렬과 사용자 삭제의 FK 검사를 함께 지원한다.
CREATE INDEX ix_projects_user_updated ON projects (user_id, updated_at DESC, id DESC);

CREATE TABLE circuits (
    project_id BIGINT NOT NULL,
    connections JSONB NOT NULL,
    source_sha256 TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- PK 인덱스가 프로젝트 삭제의 FK 조회도 지원하므로 중복 인덱스는 만들지 않는다.
    CONSTRAINT pk_circuits PRIMARY KEY (project_id),
    CONSTRAINT fk_circuits_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT ck_circuits_connections CHECK (jsonb_typeof(connections) = 'object'),
    CONSTRAINT ck_circuits_sha256 CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_circuits_parser_version CHECK (char_length(btrim(parser_version)) > 0)
);

-- 공개 API 역할은 접근하지 못한다. 서버 DB 역할에서 소유자 조건을 검증한다.
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE circuits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON projects, circuits FROM PUBLIC;
REVOKE ALL ON SEQUENCE projects_id_seq FROM PUBLIC;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON projects, circuits FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON SEQUENCE projects_id_seq FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
