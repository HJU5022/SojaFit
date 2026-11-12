# services

## 역할
- 이 폴더: LLM·임베딩 호출 계층, Langfuse 연동, Mouser 클라이언트, 데모 재생, 견적 저장(`backend/services/`)의 회귀 테스트.
- 넣는 것: `test_llm.py`, `test_langfuse_prompts.py` 같은 서비스 계층 시험. 실제 API 호출은 하지 않는다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 실제 Langfuse 점검 스크립트(`scripts/langfuse/`), 평가 실행(`tests/evals/`).
- 담당: 프롬프트·서비스

실행: `uv run pytest -q tests/services`(저장소 루트).

## 파일
| 파일 | 확인하는 것 |
|---|---|
| `SERVICES.md` | 이 문서 |
| `test_llm.py` | 임베딩 반환 계약, Voyage 요청 본문·재시도·결제 신호 멈춤, `chat()` 형식 검증·재시도 상한, 평가 전용 provider 정책·비용 정산, Decisions 요청 정책 |
| `test_langfuse_prompts.py` | 프롬프트·Skill 버전/본문 대조, 일반 호출의 로컬 경계, 예산·계측 실패 시 결과 보존, 내보내기 자격증명 제외, 서비스 분석 기록(`analysis-metadata`)에 user·session id만 있고 질문 글은 없음 |
| `test_service_trace.py` | 서비스 분석 추적: 인메모리 내보내기로 질문·답·넷리스트 값·내 설정이 어떤 칸에도 없고 모델·토큰·노드 이름·오류 수준은 남음, 오류 문구 제거, 같은 trace_id·session, 키 없음·실패 삼킴, 공급자 비용과 캐시 토큰 유지 |
| `test_mouser.py` | 가짜 transport로 요청 모양(POST, `apiKey` 쿼리, `\|`로 이은 품번), 화면 칸만 고르기, 한 번만 보내기, 실패 종류, 품번 조건·키 없음·호출 상한에서 부르지 않기, 로그와 오류 문구에 키·요청 주소가 없음 |
| `test_datasheet_rows.py` | 실제 형식의 PDF에서 답변·재조회까지 인용 위치와 검색 상한 |
| `test_demo_replay.py` | 데모 응답 기록 → 재생이 같은 결과, 기록에 없는 호출은 `ReplayMiss`, 기록 줄 허용 칸, 기록 스크립트 가드, 서비스 재생(`DEMO_REPLAY=1`)의 판정·인터럽트·재개와 기록 없음 503 |
| `test_quote_service.py` | 승인 가능한 판정과 가격·재고 키 재귀 거절 |
