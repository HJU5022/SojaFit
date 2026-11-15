# services

## 역할
- 이 폴더: 외부 호출과 서비스 보조 기능을 모은 곳. LLM·임베딩 호출(`llm.py`), Langfuse 프롬프트 관리와 추적(`langfuse_prompts.py`, `service_trace.py`), Mouser 가격·재고(`mouser.py`), Exa 외부 근거 검색(`exa.py`, `datasheet_rows.py`), 메일 발송(`mail.py`), 키 없는 데모 재생(`demo.py`), 견적 저장(`quote.py`)이 있다.
- 넣는 것: LLM·임베딩 호출의 유일한 입구와 재시도·예산 상한, Langfuse 프롬프트 등록·고정 버전 검증·노드 추적, Mouser Search API 호출(응답은 저장·로그하지 않음, ADR 0009).
- 넣지 않는 것: 데모 응답 파일(`data/demo/`), 그래프 노드(`backend/graph/`, `backend/multi_agent/`), 프롬프트 원문(`backend/prompts/`), 검색(`backend/rag/`).
- 담당: 서비스·운영

## llm.py가 한 곳이어야 하는 이유
그래프 노드와 라우터는 `openai`를 직접 import하지 않고 전부 `llm.py`를 거친다. 여기서 세 가지를 처리한다.
1. Langfuse: `langfuse_prompts.session()`을 명시적으로 켠 호출은 고정 버전 프롬프트와 Skill을 검증하고 노드·generation·모델·usage·오류를 기록한다. 일반 호출은 추적을 켜지 않는다. 서비스 분석은 이와 별개로 키가 있으면 `service_trace.py`가 모델 호출 메타만 보낸다(본문 제거).
2. 키 없는 데모: 서비스 조립이 `llm.node_chat` 대신 `demo.py`의 재생 chat을 그래프와 카드 도구에 주입한다. 그래프·BM25 검색·MCP 사실 확인은 실제 경로와 같다. 재생은 `DEMO_REPLAY=1`과 `DEMO_MODE=1`일 때만 켜지고(`demo.enabled()`), `DEMO_MODE=1`만 켠 실행은 임베딩·리랭크만 끄고 실제 LLM/BM25 경로를 유지한다.
3. 비용 상한: 재시도와 루프의 상한을 여기에 둔다. LLM 출력 형식 재시도는 `MAX_FORMAT_RETRIES`(`llm.py:48`), 임베딩 재시도는 호출하는 쪽(`backend/rag/pipeline/ingest.py`의 `MAX_RETRY`)이다. 사용자 분석은 `EvaluationBudget`을 재사용해 실행당 예약 비용·호출 수·시간·출력 토큰과 사용자별 하루 예약 비용·호출 간격을 적용하고 DB 원자 갱신으로 여러 thread·인스턴스가 한도를 공유한다. 값은 [.env.example](../../.env.example)의 `ANALYSIS_*`이고 계약은 [SPEC.md](../../SPEC.md)다.

노드별 모델 표 `NODE_MODELS`는 `langfuse_prompts.py`에 있다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `SERVICES.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `llm.py` | LLM·임베딩 호출의 유일한 입구: `node_chat`·`chat`·`node_model`, `embed_texts`, `voyage_embed`·`voyage_rerank`, 평가 전용 `evaluation_*`. `check_langfuse_connection()`은 부르는 곳 없음 |
| `langfuse_prompts.py` | 노드별 모델 표 `NODE_MODELS`, 프롬프트·Skill 등록(`publish_nodes`, `publish_skill`)과 고정 버전 대조, 세션 추적, `CostCallbackHandler`, `timed_tool`·`AnalysisTimings` |
| `service_trace.py` | 서비스 분석의 모델 호출별 Langfuse 추적. 키가 있으면 켜지고, 내보내기 직전 훅 `mask_otel_spans`가 허용 목록 밖의 칸을 지우고 입력·출력은 `[redacted]`로 바꿈. 평가(`evals/`)는 이 파일을 쓰지 않음 |
| `demo.py` | 키 없는 데모의 LLM 응답 기록 `recorder`·재생 `replayer`(없으면 `ReplayMiss`), `enabled`, `service_chat`, 데모 질문 목록·대조 `questions`·`match`·`refusal`. 유료 모델 호출 없음 |
| `mouser.py` | Mouser 품번 검색 클라이언트 `check_parts`·`search_parts`: 한 번만 보내고 프로세스당 호출 상한 `MAX_CALLS`. 실패는 `MouserError(kind)`. `/api/prices`만 부름 |
| `exa.py` | 내부 근거가 부족할 때만 쓰는 Exa 외부 근거 검색(공식 제조사 PDF, 공개 참고 링크). 요청당 호출 예산 `SearchBudgetExhausted` |
| `datasheet_rows.py` | 공식 데이터시트 PDF 표에서 품번 열·페이지·행·단위를 확인해 인용 후보를 만듦. PDF 파서는 별도 프로세스 |
| `quote.py` | 완료 판정의 품번·verdict 쌍을 불변 승인 snapshot으로 저장하고 가격 없는 견적·승인 사례를 관리. 사례가 남은 활성 승인만 조회/새 견적에 사용하며(`list_approvals`는 승인별 견적 `quotes`와 `part_number`를 함께 반환) 삭제 후 새 승인 이력을 허용한다. 같은 run 행 잠금과 활성 사례 검사로 중복 승인을 막고, 기존 snapshot/견적은 보존한다. 가격·재고 키는 거절(`assert_no_price_data`) |
| `mail.py` | Gmail SMTP TLS 인증 링크 발송 `send_link`. 설정은 `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_PORT`, `AUTH_ORIGIN`이고 미설정이면 발송하지 않음. 토큰·수신자·오류를 로그하지 않음 |
