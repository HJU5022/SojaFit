-- 컨테이너가 처음 만들어질 때 한 번 실행됩니다 (db/ 아래 .sql은 이름 순서대로).
-- 초기화 SQL은 세 자리 번호를 사용합니다: 000 확장, 002 코퍼스, 003 인증.
CREATE EXTENSION IF NOT EXISTS vector;
