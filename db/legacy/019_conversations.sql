-- Project ownership is enforced by repository queries; public API roles have no access.
-- Validate the stored public result recursively without accepting unknown nested keys.
CREATE FUNCTION conversation_json_matches(value jsonb, shape jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE item jsonb; field record; required_keys text[];
BEGIN
    IF jsonb_typeof(shape) = 'string' THEN
        RETURN jsonb_typeof(value) = (shape #>> '{}');
    ELSIF shape ? '$any' THEN
        FOR item IN SELECT * FROM jsonb_array_elements(shape->'$any') LOOP
            IF conversation_json_matches(value, item) THEN RETURN true; END IF;
        END LOOP;
        RETURN false;
    ELSIF shape ? '$array' THEN
        IF jsonb_typeof(value) <> 'array' THEN RETURN false; END IF;
        FOR item IN SELECT * FROM jsonb_array_elements(value) LOOP
            IF NOT conversation_json_matches(item, shape->'$array') THEN RETURN false; END IF;
        END LOOP;
        RETURN true;
    END IF;
    IF jsonb_typeof(value) <> 'object' THEN RETURN false; END IF;
    SELECT coalesce(array_agg(x), ARRAY[]::text[]) INTO required_keys FROM jsonb_array_elements_text(shape->'$required') AS x;
    IF NOT value ?& required_keys THEN RETURN false; END IF;
    FOR field IN SELECT * FROM jsonb_each(value) LOOP
        IF NOT shape ? field.key OR field.key LIKE '$%' OR NOT conversation_json_matches(field.value, shape->field.key) THEN RETURN false; END IF;
    END LOOP;
    RETURN true;
END $$;

CREATE TABLE threads (
    id UUID PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_threads_project ON threads(project_id);
CREATE TABLE runs (
    id UUID PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('running', 'requires_input', 'completed', 'refused', 'failed')),
    safe_result JSONB CHECK (safe_result IS NULL OR conversation_json_matches(safe_result, '{"$required":["answer","question_type","price_parts","interrupt","judgement","evidence"],"answer":"string","question_type":"string","price_parts":{"$array":"string"},"interrupt":{"$required":["missing","role_choices","question"],"missing":{"$array":"string"},"role_choices":{"$array":"string"},"question":"string"},"judgement":{"$any":[{"$required":["kind"],"kind":"string","roles":{"$array":"string"},"role_evidence":{"$array":"string"},"results":{"$array":{"$required":["part","verdict"],"part":"string","role":"string","verdict":"string","checks":{"$array":{"$required":["code"],"code":"string","tier":"string","op":"string","basis":"string","threshold":{"$any":["number",{"$array":"number"},"null"]},"value":{"$any":["number",{"$array":"number"},"null"]},"unit":{"$any":["string","null"]},"condition":{"$any":["string","null"]},"result":"string","why":"string","citation":{"$any":[{"$required":[],"document":"string","page":{"$any":["number","string","null"]},"table":"string","row":"string","chunk_index":{"$any":["number","null"]},"chunk_id":{"$any":["string","number","null"]}},"null"]}}},"missing":{"$array":"string"},"uncertain":{"$array":"string"},"cautions":{"$array":"string"},"board_change":{"$any":["boolean","null"]},"package_citation":{"$any":[{"$required":[],"document":"string","page":{"$any":["number","string","null"]},"table":"string","row":"string","chunk_index":{"$any":["number","null"]},"chunk_id":{"$any":["string","number","null"]}},"null"]}}},"shown":{"$array":{"$required":["part","verdict"],"part":"string","role":"string","verdict":"string","checks":{"$array":{"$required":["code"],"code":"string","tier":"string","op":"string","basis":"string","threshold":{"$any":["number",{"$array":"number"},"null"]},"value":{"$any":["number",{"$array":"number"},"null"]},"unit":{"$any":["string","null"]},"condition":{"$any":["string","null"]},"result":"string","why":"string","citation":{"$any":[{"$required":[],"document":"string","page":{"$any":["number","string","null"]},"table":"string","row":"string","chunk_index":{"$any":["number","null"]},"chunk_id":{"$any":["string","number","null"]}},"null"]}}},"missing":{"$array":"string"},"uncertain":{"$array":"string"},"cautions":{"$array":"string"},"board_change":{"$any":["boolean","null"]},"package_citation":{"$any":[{"$required":[],"document":"string","page":{"$any":["number","string","null"]},"table":"string","row":"string","chunk_index":{"$any":["number","null"]},"chunk_id":{"$any":["string","number","null"]}},"null"]}}},"unverified":{"$array":{"$required":["part","verdict"],"part":"string","role":"string","verdict":"string","checks":{"$array":{"$required":["code"],"code":"string","tier":"string","op":"string","basis":"string","threshold":{"$any":["number",{"$array":"number"},"null"]},"value":{"$any":["number",{"$array":"number"},"null"]},"unit":{"$any":["string","null"]},"condition":{"$any":["string","null"]},"result":"string","why":"string","citation":{"$any":[{"$required":[],"document":"string","page":{"$any":["number","string","null"]},"table":"string","row":"string","chunk_index":{"$any":["number","null"]},"chunk_id":{"$any":["string","number","null"]}},"null"]}}},"missing":{"$array":"string"},"uncertain":{"$array":"string"},"cautions":{"$array":"string"},"board_change":{"$any":["boolean","null"]},"package_citation":{"$any":[{"$required":[],"document":"string","page":{"$any":["number","string","null"]},"table":"string","row":"string","chunk_index":{"$any":["number","null"]},"chunk_id":{"$any":["string","number","null"]}},"null"]}}},"terms":{"$array":{"$required":["code"],"code":"string","gte":{"$any":["number","null"]},"lte":{"$any":["number","null"]}}},"capped":"boolean","preferred_mount":"string"},"null"]},"evidence":{"$array":{"$required":[],"document":"string","page":{"$any":["number","string","null"]},"table":"string","row":"string","section":"string","citation_number":"string"}}}'::jsonb) AND NOT jsonb_path_exists(safe_result->'price_parts', '$[*] ? (!(@ like_regex "^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$"))')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, thread_id)
);
CREATE INDEX ix_runs_thread ON runs(thread_id);
CREATE UNIQUE INDEX ix_runs_active ON runs(thread_id) WHERE status IN ('running', 'requires_input');
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    run_id UUID NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id, thread_id) REFERENCES runs(id, thread_id) ON DELETE CASCADE
);
CREATE INDEX ix_messages_thread ON messages(thread_id);
CREATE INDEX ix_messages_run ON messages(run_id);
ALTER TABLE threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON threads, runs, messages FROM PUBLIC;
REVOKE ALL ON SEQUENCE messages_id_seq FROM PUBLIC;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON threads, runs, messages FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON SEQUENCE messages_id_seq FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
