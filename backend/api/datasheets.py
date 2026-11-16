"""데이터시트 서재 HTTP 경계: `GET /api/datasheets`(로그인 필요, 읽기만, #67). 코퍼스(`source_documents`)의 폐기하지 않은 문서 목록을 찾는다.

- 품번 찾기: 문서의 표지 청크(`document_chunks.chunk_index = 0`, "[파일] 이 데이터시트의 품번: SS32, SS33, …")에 적힌 품번 글을 쓴다.
  검색 품번 색인(`backend/rag/retrieve.py` `part_index` · `backend/rag/card_specs.py` `part_docs_index`)과 같은 자료라 SS34로 "SS32 SERIES"를 찾는다.
- 화면 쪽 짝: `frontend/src/Library.tsx`(`/library`).
하지 않는 일: 코퍼스 쓰기 · 적재(`backend/rag/pipeline/ingest.py`), 청크 본문 내보내기, 판정.
출처: SPEC.md 4절.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend import auth

router = APIRouter(prefix='/api', tags=['datasheets'])
PAGE_SIZE = 50
# 폐기하지 않은 문서와 표지에 적힌 품번 글(", "로 이음). 정규식은 retrieve.COVER와 같은 모양이고, 표지 청크가 없으면 빈 글이다
DOCS = """WITH docs AS (
    SELECT d.id, d.title, d.publisher, d.revision, d.category, d.source_url, d.collected_at,
           COALESCE(substring(c.content from '이 데이터시트의 품번: (.*)'), '') AS parts
    FROM source_documents d LEFT JOIN document_chunks c ON c.document_id = d.id AND c.chunk_index = 0
    WHERE d.retired_at IS NULL)
"""
# [왜] strpos는 LIKE와 달리 %·_를 와일드카드로 읽지 않아 검색어를 이스케이프하지 않아도 된다. 빈 검색어는 1을 돌려줘 전부 걸린다
MATCH = "WHERE (%(category)s = '' OR category = %(category)s) AND strpos(upper(concat_ws(' ', title, publisher, parts)), upper(%(q)s)) > 0"
COLUMNS = ('id', 'title', 'publisher', 'revision', 'category', 'source_url', 'collected_at')


class Datasheet(BaseModel):
    id: int
    title: str  # 품번 시리즈(예: "SS32 SERIES")
    publisher: str
    revision: str | None
    category: str | None  # 코퍼스 분류 이름(pipeline/specs.py family, 예: schottky-rectifier)
    source_url: str  # 제조사 공식 원문 PDF
    collected_at: datetime
    parts: list[str]  # 표지에 적힌 품번. 표지 청크가 없으면 빈 목록


class CategoryCount(BaseModel):
    category: str
    count: int


class DatasheetPage(BaseModel):
    items: list[Datasheet]
    total: int  # 조건에 맞는 문서 수(쪽과 상관없음)
    page: int
    page_size: int
    categories: list[CategoryCount]  # 서재 전체(폐기 제외)의 분류별 문서 수, 많은 순. 검색 조건과 상관없는 거르기 목록이다


@router.get('/datasheets', dependencies=[Depends(auth.current_user_id)], response_model=DatasheetPage)
def datasheets(q: str = Query('', max_length=100, description='품번 · 제목 · 제조사의 일부(대소문자 무시)'),
               category: str = Query('', max_length=100, description='분류 이름. 비우면 전체'),
               page: int = Query(1, ge=1, le=1000, description=f'쪽 번호(한 쪽 {PAGE_SIZE}건)')):
    """로그인한 사용자에게 서재(폐기 제외 코퍼스 문서)를 제목 순으로 한 쪽씩 돌려준다. 검색은 품번(표지) · 제목 · 제조사의 부분 일치다."""
    args = {'q': q.strip(), 'category': category, 'limit': PAGE_SIZE, 'offset': (page - 1) * PAGE_SIZE}
    with auth.connection() as conn:
        # [왜] 전체 수는 따로 센다. 쪽 행의 창 함수로 세면 범위 밖 쪽(깊은 링크의 page)에서 0건이 된다
        total = conn.execute(DOCS + 'SELECT count(*) FROM docs ' + MATCH, args).fetchone()[0]
        rows = conn.execute(DOCS + f'SELECT {", ".join(COLUMNS)}, parts FROM docs {MATCH} ORDER BY title, id LIMIT %(limit)s OFFSET %(offset)s',
                            args).fetchall()
        counts = conn.execute('SELECT category, count(*) FROM source_documents WHERE retired_at IS NULL AND category IS NOT NULL'
                              ' GROUP BY category ORDER BY count(*) DESC, category').fetchall()
    return {'items': [dict(zip(COLUMNS, r), parts=[p.strip() for p in r[-1].split(',') if p.strip()]) for r in rows],
            'total': total, 'page': page, 'page_size': PAGE_SIZE,
            'categories': [{'category': c, 'count': n} for c, n in counts]}
