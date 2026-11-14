-- 새 DB 및 기존 서비스 DB용. 호출자가 트랜잭션을 연다. 운영 적용은 별도 검토한다.
ALTER TABLE circuits ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1);
CREATE TABLE IF NOT EXISTS project_circuit_versions (
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version >= 0),
    connections JSONB NOT NULL CHECK (jsonb_typeof(connections) = 'object'),
    source_sha256 TEXT CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    parser_version TEXT NOT NULL CHECK (char_length(btrim(parser_version)) > 0),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('demo', 'upload')),
    demo_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, version),
    CHECK ((source_kind = 'demo') = (demo_id IS NOT NULL)),
    CHECK ((version = 0) = (source_sha256 IS NULL))
);
INSERT INTO project_circuit_versions(project_id,version,connections,source_sha256,parser_version,source_kind,demo_id,created_at)
SELECT p.id, COALESCE(c.version,0), COALESCE(c.connections,'{"parts":[],"nets":[]}'::jsonb),
       c.source_sha256, COALESCE(c.parser_version,'empty-v1'), p.source_kind,p.demo_id,COALESCE(c.created_at,p.created_at)
FROM projects p LEFT JOIN circuits c ON c.project_id=p.id ON CONFLICT DO NOTHING;

ALTER TABLE threads ADD COLUMN IF NOT EXISTS circuit_version INTEGER;
UPDATE threads t SET circuit_version=COALESCE((SELECT c.version FROM circuits c WHERE c.project_id=t.project_id),0)
WHERE circuit_version IS NULL;
ALTER TABLE threads ALTER COLUMN circuit_version SET NOT NULL;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='threads'::regclass AND conname='fk_threads_circuit_version') THEN
        ALTER TABLE threads ADD CONSTRAINT fk_threads_circuit_version FOREIGN KEY(project_id,circuit_version)
            REFERENCES project_circuit_versions(project_id,version) ON DELETE CASCADE;
    END IF;
END $$;

-- 회로를 올리기 전 만든 대화도 이후 회로를 참조하지 않는다.
CREATE OR REPLACE FUNCTION initialize_empty_circuit_version() RETURNS TRIGGER LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
    INSERT INTO project_circuit_versions(project_id,version,connections,parser_version,source_kind,demo_id)
    VALUES (NEW.id,0,'{"parts":[],"nets":[]}','empty-v1',NEW.source_kind,NEW.demo_id);
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS initialize_empty_circuit_version ON projects;
CREATE TRIGGER initialize_empty_circuit_version AFTER INSERT ON projects FOR EACH ROW EXECUTE FUNCTION initialize_empty_circuit_version();

CREATE OR REPLACE FUNCTION preserve_circuit_version() RETURNS TRIGGER LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND (NEW.project_id <> OLD.project_id OR NEW.version <= OLD.version) THEN
        RAISE EXCEPTION 'circuit version must increase' USING ERRCODE='23514';
    END IF;
    INSERT INTO project_circuit_versions(project_id,version,connections,source_sha256,parser_version,source_kind,demo_id,created_at)
    SELECT NEW.project_id,NEW.version,NEW.connections,NEW.source_sha256,NEW.parser_version,p.source_kind,p.demo_id,NEW.created_at
    FROM projects p WHERE p.id=NEW.project_id;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS preserve_circuit_version ON circuits;
CREATE TRIGGER preserve_circuit_version AFTER INSERT OR UPDATE ON circuits FOR EACH ROW EXECUTE FUNCTION preserve_circuit_version();

CREATE OR REPLACE FUNCTION pin_thread_circuit_version() RETURNS TRIGGER LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.project_id <> OLD.project_id OR NEW.circuit_version <> OLD.circuit_version THEN
            RAISE EXCEPTION 'thread circuit version is immutable' USING ERRCODE='23514';
        END IF;
    ELSIF NEW.circuit_version IS NULL THEN
        PERFORM id FROM projects WHERE id=NEW.project_id FOR UPDATE;
        NEW.circuit_version := COALESCE((SELECT version FROM circuits WHERE project_id=NEW.project_id),0);
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS pin_thread_circuit_version ON threads;
CREATE TRIGGER pin_thread_circuit_version BEFORE INSERT OR UPDATE ON threads FOR EACH ROW EXECUTE FUNCTION pin_thread_circuit_version();

CREATE OR REPLACE FUNCTION reject_circuit_version_update() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'circuit versions are immutable' USING ERRCODE='23514';
END $$;
DROP TRIGGER IF EXISTS reject_circuit_version_update ON project_circuit_versions;
CREATE TRIGGER reject_circuit_version_update BEFORE UPDATE ON project_circuit_versions FOR EACH ROW EXECUTE FUNCTION reject_circuit_version_update();

ALTER TABLE project_circuit_versions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON project_circuit_versions FROM PUBLIC;
REVOKE ALL ON FUNCTION initialize_empty_circuit_version(),preserve_circuit_version(),pin_thread_circuit_version(),reject_circuit_version_update() FROM PUBLIC;
DO $$ DECLARE role_name TEXT; BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('REVOKE ALL ON project_circuit_versions FROM %I',role_name);
            EXECUTE format('REVOKE ALL ON FUNCTION initialize_empty_circuit_version(),preserve_circuit_version(),pin_thread_circuit_version(),reject_circuit_version_update() FROM %I',role_name);
        END IF;
    END LOOP;
END $$;
INSERT INTO app_migrations(version,note) VALUES ('031-circuit-versions','Immutable circuits and pinned conversations') ON CONFLICT DO NOTHING;
