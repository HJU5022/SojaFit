-- users에 역할 열(role: admin | user)을 더한다. 기존 계정은 모두 user이고 관리자는 따로 만들어야 한다.
-- 새 볼륨 첫 기동 때 자동 실행된다(003 다음). 기존 DB는 별도 마이그레이션으로 적용한다.
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user'));
