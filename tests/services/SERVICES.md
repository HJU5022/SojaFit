# services

## 역할
- 이 폴더: LLM·임베딩 호출 계층과 Langfuse 연동(`backend/services/`)의 회귀 테스트를 둡니다.
- 넣는 것: `test_llm.py`, `test_langfuse_prompts.py` 같은 서비스 계층 시험. 실제 API 호출은 하지 않습니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 실제 Langfuse 점검 스크립트(`scripts/langfuse/`), 평가 실행(`tests/evals/`).
- 담당: 프롬프트·서비스

실행: `uv run pytest -q tests/services`(저장소 루트).

## 파일
- `SERVICES.md` — 이 문서
- `test_langfuse_prompts.py` — 프롬프트·Skill 버전/본문 대조, 일반 호출의 로컬 경계, 예산·계측 실패 시 결과 보존, 타임라인 확인, 내보내기 자격증명 제외를 API 없이 확인
- `test_llm.py` — 가짜 모델로 임베딩 반환 계약, Voyage 임베딩·리랭크 요청 본문과 재시도·결제 신호 멈춤(가짜 httpx), `chat()`의 형식 검증·재시도 상한(호출 3번)·구독 CLI 명령 확인
