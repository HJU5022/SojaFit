# services

## 역할
- 이 폴더: LLM·임베딩 호출 계층, Langfuse 연동, Mouser 가격·재고 클라이언트(`backend/services/`)의 회귀 테스트를 둡니다.
- 넣는 것: `test_llm.py`, `test_langfuse_prompts.py` 같은 서비스 계층 시험. 실제 API 호출은 하지 않습니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 실제 Langfuse 점검 스크립트(`scripts/langfuse/`), 평가 실행(`tests/evals/`).
- 담당: 프롬프트·서비스

실행: `uv run pytest -q tests/services`(저장소 루트).

## 파일
- `test_datasheet_rows.py` — 실제 형식의 PDF에서 답변·재조회까지 인용 위치와 검색 상한 검증
- `SERVICES.md` — 이 문서
- `test_langfuse_prompts.py` — 프롬프트·Skill 버전/본문 대조, 일반 호출의 로컬 경계, 예산·계측 실패 시 결과 보존, 타임라인 확인, 내보내기 자격증명 제외, 서비스 분석 기록(`analysis-metadata`)의 user · session id와 질문 글 미포함을 API 없이 확인
- `test_service_trace.py` — 서비스 분석 추적(`service_trace.py`): 인메모리 내보내기로 질문 · 답 · 넷리스트 값 · 내 설정이 어떤 칸에도 없고 모델 · 토큰 · 노드 이름 · 오류 수준은 남음, 오류 문구 제거, 같은 trace_id · session, 키 없음 · 실패 삼킴. 서비스·평가 공통 콜백의 공급자 비용과 캐시 토큰 유지, 0/미보고/음수/NaN 비용도 확인
- `test_mouser.py` — 가짜 transport(손으로 쓴 응답)로 Mouser 요청 모양(POST · `apiKey` 쿼리 · `|`로 이은 품번), 화면 칸만 고르기, 한 번만 보내기, 실패 종류(키 거부 · HTTP · Errors · 형식), 품번 조건 · 키 없음 · 호출 상한에서 부르지 않기, 로그와 오류 문구에 키 · 요청 주소가 없는지 확인
- `test_quote_service.py` — 승인 가능한 3종 판정과 가격·재고 키 재귀 거절 시험
- `test_demo_replay.py` — 가짜 LLM으로 데모 응답 기록 → 재생이 같은 그래프 결과를 내는지, 기록에 없는 호출은 거절 답이 아니라 노드 이름을 담은 `ReplayMiss`로 멈추는지, 기록 줄에 호출 칸(sha256 · node · schema · response) 밖의 값이 없는지, 기록 스크립트(`scripts/demo/record_demo.py`)가 `DEMO_MODE=1` · 키 없이는 멈추고 v3 데모 질문이 동결 입력 그대로인지 확인. 서비스 재생(`DEMO_REPLAY=1`): 서비스 조립으로 판정 · 조건 인터럽트 · 기록한 답 재개를 기록 → 재생하면 같은 경로 · 판정인지, 기록이 없으면 503, 같은 회로 · 대상 · 질문 · 조건만 받는지, 데모 질문마다 같은 회로의 React 데모 프로젝트(c01 포함)가 있는지, 실행 중 `ReplayMiss`가 노드 이름을 담은 503인지
- `test_llm.py` — 가짜 모델로 임베딩 반환 계약, Voyage 임베딩·리랭크 요청 본문과 재시도·결제 신호 멈춤(가짜 httpx), `chat()`의 형식 검증·재시도 상한(호출 3번)·구독 CLI 명령, 평가 전용 provider 정책·비용 정산 확인

`test_llm.py`는 Jev Decisions catalog의 ZDR filter와 Decisions POST의 정책·단일 호출도 네트워크 없이 검사한다.
