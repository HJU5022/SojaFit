-- 컨테이너가 처음 만들어질 때 한 번 실행됩니다 (db/ 아래 .sql은 이름 순서대로).
-- 실행 SQL은 세 자리 번호를 사용합니다: 000 확장, 001 업무 스키마, 002 이후 단계.
CREATE EXTENSION IF NOT EXISTS vector;
