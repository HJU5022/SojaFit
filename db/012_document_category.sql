-- source_documents에 문서의 다이오드 분류(category)를 더한다(db/schema/table-definition.md 5.4).
-- 역할: 카드 찾기(backend/rag/card_find.py)가 문서 단위로 분류를 거른다. 값은 pipeline/specs.py의 family(청크 category)가 내는 분류 이름이다(예: schottky-rectifier).
-- 하지 않는 일: 값 채우기. 새 적재는 backend/rag/pipeline/ingest.py가 넣고, 이미 있는 행은 따로 채운다.
-- [주의] Compose는 빈 볼륨에서만 이 파일을 자동 실행한다. 기존 DB(로컬 볼륨·Supabase)에는 따로 적용한다. 다시 실행해도 아무것도 바꾸지 않는다.
-- [왜] NULL 허용: 열을 더한 직후에는 기존 행에 값이 없고, 청크 파일에 분류가 없는 문서도 넣을 수 있게 한다.
ALTER TABLE source_documents ADD COLUMN IF NOT EXISTS category TEXT;
