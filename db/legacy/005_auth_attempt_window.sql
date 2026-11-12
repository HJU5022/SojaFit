-- auth_login_attempts에 실패 집계 창 시작 시각(window_started_at)을 더한다. 15분이 지나면 실패 횟수를 다시 센다.
-- 새 볼륨 첫 기동 때 자동 실행된다(003 다음). 기존 DB는 별도 마이그레이션으로 적용한다.
ALTER TABLE auth_login_attempts ADD COLUMN window_started_at TIMESTAMPTZ;
