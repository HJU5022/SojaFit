# services

## 역할
- 이 폴더: LLM과 임베딩 호출을 모으는 한 곳, 견적서 저장, 가격·재고 조회를 둡니다.
- 넣는 것: `llm.py`(LLM·임베딩 호출과 데모 모드 재생), 견적서 저장(`quote.py`), 가격·재고 조회(`mouser.py`, 확장 단계).
- 넣지 않는 것: 데모 응답 파일(`data/demo/`), 그래프 노드(`backend/graph/`).
- 담당: 서비스·운영

## llm.py가 한 곳이어야 하는 이유 (강사 안내)
라우터나 그래프 노드가 `openai`를 직접 import하지 않고 전부 `llm.py`를 거칩니다. 여기서 세 가지를 처리합니다.
1. 현재 단계: `llm.py`의 `check_langfuse_connection()`으로 Cloud 인증만 확인합니다. 프롬프트·응답 트레이스는 별도 결정 전까지 기록하지 않습니다.
2. 데모 모드: `DEMO_MODE=1`이면 키 없이 `data/demo/`의 응답을 재생합니다(G2). 평가자는 키가 없습니다. 재생 코드는 아직 없고, 지금은 `DEMO_MODE`가 검색의 임베딩 호출만 끕니다(`backend/rag/retrieve.py`).
3. 비용 상한: 키는 조당 하나이고 한도가 있어서 재시도와 루프의 상한을 여기에 둡니다. 지금 임베딩 재시도 상한은 호출하는 쪽(`backend/rag/ingest.py`의 `MAX_RETRY`)에 있습니다.

## 파일
- `llm.py` — LLM·임베딩 호출을 모으는 자리. 지금은 임베딩(`embed_texts()`)과 Langfuse 인증 확인만 있고 LLM 대화 호출은 아직 없습니다. 평가 스크립트도 `embed_texts()`를 통해 API 임베딩을 호출합니다.
