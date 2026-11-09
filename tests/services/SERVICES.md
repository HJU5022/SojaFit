# services

## 역할
- 이 폴더: LLM·임베딩 호출 계층, Langfuse 연동, Mouser 가격·재고 클라이언트(`backend/services/`)의 회귀 테스트를 둡니다.
- 넣는 것: `test_llm.py`, `test_langfuse_prompts.py` 같은 서비스 계층 시험. 실제 API 호출은 하지 않습니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 실제 Langfuse 점검 스크립트(`scripts/langfuse/`), 평가 실행(`tests/evals/`).
- 담당: 프롬프트·서비스

실행: `uv run pytest -q tests/services`(저장소 루트).

## 파일
- `SERVICES.md` — 이 문서
- `test_langfuse_prompts.py` — 프롬프트·Skill 버전/본문 대조, 일반 호출의 로컬 경계, 예산·계측 실패 시 결과 보존, 타임라인 확인, 내보내기 자격증명 제외를 API 없이 확인
- `test_mouser.py` — 가짜 transport(손으로 쓴 응답)로 Mouser 요청 모양(POST · `apiKey` 쿼리 · `|`로 이은 품번), 화면 칸만 고르기, 한 번만 보내기, 실패 종류(키 거부 · HTTP · Errors · 형식), 품번 조건 · 키 없음 · 호출 상한에서 부르지 않기, 로그와 오류 문구에 키 · 요청 주소가 없는지 확인
- `test_quote_service.py` — 승인 가능한 3종 판정과 가격·재고 키 재귀 거절 시험
- `test_llm.py` — 가짜 모델로 임베딩 반환 계약, Voyage 임베딩·리랭크 요청 본문과 재시도·결제 신호 멈춤(가짜 httpx), `chat()`의 형식 검증·재시도 상한(호출 3번)·구독 CLI 명령, 평가 전용 provider 정책·비용 정산 확인

`test_llm.py`는 Jev Decisions catalog의 ZDR filter와 Decisions POST의 정책·단일 호출도 네트워크 없이 검사한다.
