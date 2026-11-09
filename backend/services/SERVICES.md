# services

## 역할
- 이 폴더: 외부 호출을 모으는 한 곳입니다. LLM·임베딩 호출(`llm.py`), Langfuse 프롬프트 관리·추적(`langfuse_prompts.py`), Mouser 가격·재고 조회(`mouser.py`)가 있습니다.
- 넣는 것: LLM·임베딩 호출의 유일한 입구, 평가 예산·재시도 상한, Langfuse 프롬프트 등록·고정 버전 검증·노드 추적, Mouser Search API 호출(응답은 저장·로그하지 않음, ADR 0009).
- 넣지 않는 것: 데모 응답 파일(`data/demo/`), 그래프 노드(`backend/graph/`), 프롬프트 원문(`backend/prompts/`), 검색(`backend/rag/`).
- 담당: 서비스·운영

## 구현 상태
- 사용자 분석은 기존 `EvaluationBudget`을 재사용해 실행당 예약 $0.50/16회/90초, 출력 4096토큰, 사용자별 UTC 하루 예약 $3와 2초 간격을 적용한다. DB 원자 갱신으로 여러 thread/인스턴스의 사용자 한도를 공유한다. Voyage·MCP도 남은 시간을 적용한다. 실패 예약은 환불하지 않으며 실제 청구액은 아니다. 이미 진행 중인 작업을 강제 종료하는 방식은 아니다. `ANALYSIS_*` 설정은 `.env.example`을 따른다.
- 없는 파일: 견적서 저장(`quote.py`)은 아직 만들지 않았습니다. 만들면 이 목록과 SOJAFIT.md 트리에 같이 적습니다.
- Mouser: `mouser.py`는 `/api/prices`(backend/main.py)만 부릅니다. 그래프는 부르지 않고 물은 품번(`price_parts`)만 남깁니다. 키 없음 · `DEMO_MODE=1`이면 Mouser를 부르지 않습니다(SPEC 4절 · 7절).
- 앱 합성 시나리오는 `DEMO_SCENARIOS=1`과 `DEMO_MODE=1`에서만 `demo.py`가 처리한다. `DEMO_MODE=1`만 켠 기존 평가는 임베딩·리랭크만 끄고 실제 LLM/BM25 경로를 유지한다.
- `check_langfuse_connection()`(Cloud 인증만 확인)은 `llm.py`에 있지만 이 저장소의 코드 중 부르는 곳이 없습니다.

## llm.py가 한 곳이어야 하는 이유
라우터나 그래프 노드가 `openai`를 직접 import하지 않고 전부 `llm.py`를 거칩니다. 여기서 세 가지를 처리합니다.
1. Langfuse: `langfuse_prompts.session()`을 명시적으로 켠 호출은 고정 버전 프롬프트와 Skill을 검증하고 노드·generation·모델·usage·오류를 기록합니다. 일반 호출은 추적을 켜지 않습니다.
2. 앱 합성 데모는 서비스 조립에서 `demo.py`의 검증된 응답/도구를 주입하며 `llm.py`나 MCP를 호출하지 않는다. 실제 평가 경로와 별개다.
3. 비용 상한: 키는 조당 하나이고 한도가 있어서 재시도와 루프의 상한을 여기에 둡니다. LLM 출력 형식 재시도 상한은 `llm.py`의 `MAX_FORMAT_RETRIES`(2회)이고, 임베딩 재시도 상한은 호출하는 쪽(`backend/rag/pipeline/ingest.py`의 `MAX_RETRY`)에 있습니다.

## 파일
- `demo.py` — 명시적 `DEMO_SCENARIOS=1`·`DEMO_MODE=1` 앱 데모의 합성 응답/도구. 유료 모델·MCP 호출을 하지 않는다. 기존 BM25 평가 모드는 유지한다.
- `__init__.py` — 패키지 표시
- `quote.py` — 완료된 성공 판정의 품번·verdict 쌍을 immutable 승인 snapshot으로 저장하고 가격 없는 견적·사용자 승인 사례를 관리한다. 모든 중첩 값에서 가격·재고 키를 거절한다.
- `llm.py` — LLM·임베딩 호출의 유일한 입구. 그래프 노드가 쓰는 `chat(system, user, schema)`·`node_chat`(Pydantic 형식 검증, 공급자 `LLM_PROVIDER`: openrouter는 LangChain `ChatOpenAI.with_structured_output`, claude_cli는 개발용, 모델은 노드별 `langfuse_prompts.NODE_MODELS`를 `node_model(node)`로 고르고 `LLM_MODEL`을 정하면 모든 노드가 그 모델 하나, ADR 0014), 임베딩 `embed_texts()`(적재 도구용), 검색용 Voyage 호출 `voyage_embed(texts, input_type)`(voyage-4-large 1024차원)·`voyage_rerank(query, docs)`(rerank-3, 정렬된 위치 번호 목록. `VOYAGE_API_KEY`, 429·5xx는 5번까지 다시, 결제 신호는 바로 멈춤), 평가 전용 `evaluation_chat()`·예약비용 상한 `evaluation_limits()`(계약은 [SPEC](../../SPEC.md)), 호출하는 곳 없는 `check_langfuse_connection()`

Jev 평가용 `evaluation_decisions_catalog()`·`evaluation_decision()`도 `llm.py`에 둔다. ZDR·data collection 거부·fallback 금지 요청을 이 서비스 경계에서 한 번만 보낸다.
- `mouser.py` — Mouser Search API 품번 검색(`POST /api/v1/search/partnumber`, 키는 `apiKey` 쿼리) 클라이언트. `check_parts`(1~10개, 3~40자, `|` 금지), `search_parts(parts, transport=None)`가 한 번만 보내고(재시도 없음, 제한 시간 10초, 프로세스당 누적 `MAX_CALLS` 300회) 품번 · 제조사 · 수량별 가격과 통화 · 재고 표시 · 상품 주소와 조회 시각만 돌려줌. 실패는 `MouserError(kind)`로만 알리고 요청 주소 · 키 · Mouser 문구를 담지 않음. httpx 요청 로그에서 Mouser 주소 줄을 버리는 필터. 읽는 환경변수 `MOUSER_API_KEY`
- `langfuse_prompts.py` — 노드별 모델 표(`NODE_MODELS`, 노드 `route` · `grade` · `rewrite` · `generate` · `supervisor` · `judge_read`), development 프롬프트·Skill 등록/조회, 고정 버전·본문 대조, 명시적 세션 추적. 상세 계약은 [SPEC](../../SPEC.md)
