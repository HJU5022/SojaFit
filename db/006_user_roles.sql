-- Existing accounts remain ordinary users until an administrator is provisioned.
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user'));
