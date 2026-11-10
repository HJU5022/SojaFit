-- 사람 승인 뒤에만 견적과 재사용 사례를 저장한다. 가격·재고 필드는 어느 깊이에서도 거절한다.
CREATE FUNCTION quote_snapshot_has_forbidden_key(value JSONB) RETURNS BOOLEAN
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE field RECORD; item JSONB;
BEGIN
    IF jsonb_typeof(value) = 'object' THEN
        FOR field IN SELECT * FROM jsonb_each(value) LOOP
            IF lower(field.key) = ANY (ARRAY['price','price_breaks','stock','availability','product_url','fetched_at'])
               OR quote_snapshot_has_forbidden_key(field.value) THEN RETURN TRUE; END IF;
        END LOOP;
    ELSIF jsonb_typeof(value) = 'array' THEN
        FOR item IN SELECT * FROM jsonb_array_elements(value) LOOP
            IF quote_snapshot_has_forbidden_key(item) THEN RETURN TRUE; END IF;
        END LOOP;
    END IF;
    RETURN FALSE;
END $$;

CREATE TABLE approvals (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message_id BIGINT NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
    snapshot JSONB NOT NULL CHECK (jsonb_typeof(snapshot) = 'object' AND NOT quote_snapshot_has_forbidden_key(snapshot)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, user_id)
);
CREATE INDEX ix_approvals_user ON approvals(user_id);

CREATE TABLE quotes (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    approval_id BIGINT NOT NULL,
    part_number TEXT NOT NULL CHECK (part_number ~ '^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$'),
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 100000),
    snapshot JSONB NOT NULL CHECK (jsonb_typeof(snapshot) = 'object' AND NOT quote_snapshot_has_forbidden_key(snapshot)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (approval_id, user_id) REFERENCES approvals(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_quotes_user ON quotes(user_id);
CREATE INDEX ix_quotes_approval ON quotes(approval_id);

CREATE TABLE approved_cases (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    approval_id BIGINT NOT NULL UNIQUE,
    snapshot JSONB NOT NULL CHECK (jsonb_typeof(snapshot) = 'object' AND NOT quote_snapshot_has_forbidden_key(snapshot)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (approval_id, user_id) REFERENCES approvals(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_approved_cases_user ON approved_cases(user_id);

ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE approved_cases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON approvals, quotes, approved_cases FROM PUBLIC;
REVOKE ALL ON SEQUENCE approvals_id_seq, quotes_id_seq, approved_cases_id_seq FROM PUBLIC;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON approvals, quotes, approved_cases FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON SEQUENCE approvals_id_seq, quotes_id_seq, approved_cases_id_seq FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
