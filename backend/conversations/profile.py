"""사용자 사실 기억(profile): 다음 대화에서도 유효한 사람에 대한 사실 3칸을 LangGraph Store에 둔다.

역할: 칸 검사(소속 · 직무 · 선호 실장 방식), 코드가 정한 틀로 한국어 문장(`text`) 만들기, Store 쓰기 · 덮어쓰기(version 올림) · 지우기,
  질문 글로 의미 검색(Voyage 임베딩 색인. 키가 없거나 데모 모드면 순위 없이 사실을 돌려줌).
하지 않는 일: HTTP · 세션(`backend/api/profile.py`), 대화에서 사실 뽑기(이번 범위 밖), 모델 프롬프트에 넣기.
  그래프가 읽는 것은 선호 실장 방식 한 칸뿐이고 읽는 노드는 `backend/graph/memory.py`의 기억 읽기다(찾기 후보 순서에만 씀, SPEC 8.5).
  승인한 판정 사례 · 전압 · 전류(회로마다 다름, 규칙 AC-02) · 주문 수량은 기억이 아니다.
출처: SPEC.md 8.5절, docs/specs/user-thread-memory.md "사용자 사실 기억".
"""
import logging
import os
import unicodedata
from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import HTTPException
from langchain_core.embeddings import Embeddings
from langgraph.store.base import PutOp

LOGGER = logging.getLogger('backend.conversations.profile')

# 칸 → 고를 수 있는 값(코드 → 화면 이름). 소속은 자유 글이라 None
CHOICES = {
    'affiliation': None,
    'job_role': {'design': '설계', 'purchasing': '구매', 'student': '학생', 'other': '기타'},
    'mounting_preference': {'smd': 'SMD', 'through_hole': '스루홀', 'any': '상관없음'},
}


def namespace(user) -> tuple[str, str]:
    """사용자 사실의 Store namespace. 첫 칸(사용자 id)이 격리 단위다."""
    # [주의] namespace는 권한 검사가 아니다. user는 세션에서 확인한 id만 받는다(요청 본문의 id를 쓰지 않음)
    return (str(user), 'profile')


def clean(kind: str, value) -> str:
    """칸 하나를 검사해 저장할 값을 돌려준다. 틀리면 ValueError(API에서 422)."""
    if kind not in CHOICES or not isinstance(value, str):
        raise ValueError('알 수 없는 칸입니다.')
    if CHOICES[kind] is None:
        # [왜] 소속 글은 화면 머리와 임베딩에 그대로 들어간다. 줄바꿈 같은 제어 문자(Cc)는 앞뒤 공백을 떼기 전에 막는다
        if any(unicodedata.category(c) == 'Cc' for c in value) or not 1 <= len(value.strip()) <= 100:
            raise ValueError('소속은 제어 문자 없이 1~100자로 입력하세요.')
        return value.strip()
    if value not in CHOICES[kind]:
        raise ValueError('고를 수 있는 값이 아닙니다.')
    return value


def sentence(kind: str, value: str) -> str:
    """정한 틀로 사실 한 문장을 만든다. 모델이 쓴 자유 글은 기억으로 두지 않는다."""
    if kind == 'affiliation':
        return f'이 사용자의 소속은 {value}이다.'
    if kind == 'job_role':
        return f'이 사용자의 직무는 {CHOICES[kind][value]}이다.'
    if value == 'any':
        return '이 사용자는 실장 방식을 가리지 않는다.'
    return f'이 사용자는 {CHOICES[kind][value]} 실장을 선호한다.'


_input_type = ContextVar('profile_embed_input_type', default='document')


class VoyageEmbeddings(Embeddings):
    """`llm.voyage_embed`(voyage-4-large 1024차원)를 Store 색인 모양으로 감싼다. 저장 문장은 document, 검색 질문은 query로 보낸다."""

    def embed_documents(self, texts):
        from backend.services import llm
        # [왜] PostgresStore(동기)는 검색 질문도 embed_documents로 임베딩한다. facts()가 검색하는 동안만 query로 바꿔 둔다
        return llm.voyage_embed(texts, _input_type.get())

    def embed_query(self, text):
        from backend.services import llm
        return llm.voyage_embed([text], 'query')[0]


# [왜] 사용자마다 사실은 3개뿐이고 namespace 조건과 함께 찾는다. 근사 색인(HNSW)은 다른 사용자 벡터에 밀려 결과가 빌 수 있어 정확 검색(flat)으로 둔다
INDEX = {'dims': 1024, 'embed': VoyageEmbeddings(), 'fields': ['text'], 'ann_index_config': {'kind': 'flat'}}


def embedding_enabled() -> bool:
    """Voyage 키가 있고 데모 모드가 아닐 때만 의미 색인을 켠다(키 없는 데모는 유료 호출 0)."""
    from backend.services import llm  # noqa: F401  [왜] .env를 먼저 읽게 한다(llm이 import 때 load_dotenv)
    return bool(os.getenv('VOYAGE_API_KEY')) and os.getenv('DEMO_MODE', '1') != '1'


class ProfileMemory:
    """한 사용자의 사실 3칸 읽기 · 고치기 · 지우기. store는 색인을 켠 PostgresStore(indexed=True) 또는 색인 없는 Store."""

    def __init__(self, store, indexed: bool):
        self.store, self.indexed = store, indexed

    def facts(self, user, query: str | None = None, limit: int = 3) -> list[dict]:
        """사용자 사실(최대 limit). query가 있고 색인이 켜져 있으면 의미가 가까운 순, 아니면 최근에 고친 순."""
        ns = namespace(user)
        everything = [item.value for item in self.store.search(ns, limit=len(CHOICES))]
        if not (query and self.indexed):
            return everything[:limit]
        token = _input_type.set('query')
        try:
            ranked = [item.value for item in self.store.search(ns, query=query, limit=limit)]
        except Exception:
            # [주의] 임베딩 장애는 순위 없는 사실로 대신한다. 질문 글 · 키 · 오류 원문은 로그에 넣지 않는다
            LOGGER.warning('profile_search_unranked')
            return everything[:limit]
        finally:
            _input_type.reset(token)
        # [왜] 색인을 끈 동안 쓴 사실은 벡터가 없어 의미 검색에 안 나온다. 순위 뒤에 붙여 빠지지 않게 한다
        seen = {fact['kind'] for fact in ranked}
        return (ranked + [fact for fact in everything if fact['kind'] not in seen])[:limit]

    def update(self, user, changes: dict) -> list[dict]:
        """칸마다 같은 key를 덮어쓰고 version을 올린다. 색인이 켜져 있으면 바뀐 문장을 다시 임베딩한다(한 번에 묶어 호출)."""
        ns, now, ops = namespace(user), datetime.now(timezone.utc).isoformat(), []
        for kind, value in changes.items():
            value = clean(kind, value)
            old = self.store.get(ns, kind)
            # shortcut: 같은 칸을 동시에 고치면 version이 한 번만 오를 수 있다. 버전으로 충돌을 막아야 하면 행 잠금으로 바꾼다
            ops.append(PutOp(ns, kind, {'kind': kind, 'value': value, 'text': sentence(kind, value),
                                        'version': old.value['version'] + 1 if old else 1,
                                        'updated_at': now, 'source': 'user_settings'}))
        if ops:
            try:
                # [주의] 색인이 켜져 있으면 임베딩이 SQL보다 먼저다. 임베딩이 실패하면 아무 칸도 바뀌지 않는다
                self.store.batch(ops)
            except Exception:
                LOGGER.warning('profile_update_failed')
                raise HTTPException(503, '설정을 저장하지 못했습니다. 잠시 후 다시 시도하세요.') from None
        return self.facts(user)

    def delete(self, user, kind: str | None = None) -> None:
        """칸 하나(kind) 또는 전부를 지운다. 색인 벡터 행은 Store 표의 FK cascade로 함께 지워진다."""
        if kind is not None and kind not in CHOICES:
            raise ValueError('알 수 없는 칸입니다.')
        self.store.batch([PutOp(namespace(user), key, None) for key in ([kind] if kind else CHOICES)])
