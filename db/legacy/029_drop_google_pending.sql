-- 서비스 표 재설계 3/3: 쓰지 않는 구글 승인 대기 표 삭제(11-10 자동 연결 결정으로 흐름이 없다, 이메일 평문 보유). 운영 이전 2b와 같다.
-- [왜] 표 이름에 스키마를 붙이지 않았다: 시험이 격리 스키마에 적용한다(tests/db_schema.py).
DROP TABLE auth_google_pending;
INSERT INTO app_migrations (version, note) VALUES ('2026-11-drop-google-pending', 'db/029: 승인 대기 표 제거');
