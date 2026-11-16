-- 새 DB 및 기존 서비스 DB용. 사용자가 고친 대화 이름 칸만 더한다(기존 행은 NULL = 첫 질문으로 만든 이름을 그대로 보임).
-- 재실행 가능(칸이 있으면 건너뜀). 기존 DB에는 psql -1 -v ON_ERROR_STOP=1 -f db/033_thread_titles.sql로 적용한다.
-- 되돌리기: ALTER TABLE threads DROP COLUMN IF EXISTS title; (고친 이름만 사라지고 대화는 남는다)
ALTER TABLE threads ADD COLUMN IF NOT EXISTS title TEXT
    CONSTRAINT ck_threads_title CHECK (title = btrim(title) AND char_length(title) BETWEEN 1 AND 200);
