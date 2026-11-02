-- Preserve locked_until semantics while bounding the failed-attempt window.
ALTER TABLE auth_login_attempts ADD COLUMN window_started_at TIMESTAMPTZ;
