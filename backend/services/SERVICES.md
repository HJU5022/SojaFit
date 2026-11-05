# services

## 역할
- 이 폴더: 외부 호출을 모으는 한 곳입니다. LLM·임베딩 호출(`llm.py`)과 Langfuse 프롬프트 관리·추적(`langfuse_prompts.py`)이 있습니다.
- 넣는 것: LLM·임베딩 호출의 유일한 입구, 평가 예산·재시도 상한, Langfuse 프롬프트 등록·고정 버전 검증·노드 추적.
- 넣지 않는 것: 데모 응답 파일(`data/demo/`), 그래프 노드(`backend/graph/`), 프롬프트 원문(`backend/prompts/`), 검색(`backend/rag/`).
- 담당: 서비스·운영

## 구현 상태
- 없는 파일: 견적서 저장(`quote.py`)과 가격·재고 조회(`mouser.py`, 확장 단계)는 아직 만들지 않았습니다. 만들면 이 목록과 SOJAFIT.md 트리에 같이 적습니다.
- 데모 모드 응답 재생: 코드가 없습니다(`llm.py` 머리말도 같음). `DEMO_MODE=1`은 지금 검색의 임베딩·리랭크 호출만 끕니다(`backend/rag/retrieve.py`가 `llm.DEMO_MODE`를 읽어 BM25만 씀).
- `check_langfuse_connection()`(Cloud 인증만 확인)은 `llm.py`에 있지만 이 저장소의 코드 중 부르는 곳이 없습니다.

## llm.py가 한 곳이어야 하는 이유 (강사 안내)
라우터나 그래프 노드가 `openai`를 직접 import하지 않고 전부 `llm.py`를 거칩니다. 여기서 세 가지를 처리합니다.
1. Langfuse: `langfuse_prompts.session()`을 명시적으로 켠 호출은 고정 버전 프롬프트와 Skill을 검증하고 노드·generation·모델·usage·오류를 기록합니다. 일반 호출은 추적을 켜지 않습니다.
2. 데모 모드: `DEMO_MODE=1`이면 키 없이 `data/demo/`의 응답을 재생한다는 것이 목표(G2)이지만 재생 코드는 아직 없습니다.
3. 비용 상한: 키는 조당 하나이고 한도가 있어서 재시도와 루프의 상한을 여기에 둡니다. LLM 출력 형식 재시도 상한은 `llm.py`의 `MAX_FORMAT_RETRIES`(2회)이고, 임베딩 재시도 상한은 호출하는 쪽(`backend/rag/pipeline/ingest.py`의 `MAX_RETRY`)에 있습니다.

## 파일
- `__init__.py` — 패키지 표시
- `llm.py` — LLM·임베딩 호출의 유일한 입구. 그래프 노드가 쓰는 `chat(system, user, schema)`·`node_chat`(Pydantic 형식 검증, 공급자 `LLM_PROVIDER`: openrouter는 LangChain `ChatOpenAI.with_structured_output`, claude_cli는 개발용, 모델은 노드별 `langfuse_prompts.NODE_MODELS`를 `node_model(node)`로 고르고 `LLM_MODEL`을 정하면 모든 노드가 그 모델 하나, ADR 0014), 임베딩 `embed_texts()`(적재 도구용), 검색용 Voyage 호출 `voyage_embed(texts, input_type)`(voyage-4-large 1024차원)·`voyage_rerank(query, docs)`(rerank-3, 정렬된 위치 번호 목록. `VOYAGE_API_KEY`, 429·5xx는 5번까지 다시, 결제 신호는 바로 멈춤), 평가 전용 `evaluation_chat()`·예약비용 상한 `evaluation_limits()`(계약은 [SPEC](../../SPEC.md)), 호출하는 곳 없는 `check_langfuse_connection()`

Jev 평가용 `evaluation_decisions_catalog()`·`evaluation_decision()`도 `llm.py`에 둔다. ZDR·data collection 거부·fallback 금지 요청을 이 서비스 경계에서 한 번만 보낸다.
- `langfuse_prompts.py` — 노드별 모델 표(`NODE_MODELS`, 노드 `route` · `grade` · `rewrite` · `generate` · `supervisor` · `judge_read`), development 프롬프트·Skill 등록/조회, 고정 버전·본문 대조, 명시적 세션 추적. 상세 계약은 [SPEC](../../SPEC.md)
