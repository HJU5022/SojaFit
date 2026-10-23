"""검색: 하이브리드(BM25 + 벡터), 리랭킹, 메타데이터 필터.

바꾸기 전에 evals/PREREGISTER.md에 기대를 먼저 적고, 한 번에 하나만 바꿔 다시 재세요.
"""


def retrieve(question: str, *, k: int = 5) -> list[dict]:
    raise NotImplementedError("TODO: 검색 구현")
