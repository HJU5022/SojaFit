# langfuse

## 역할
- 이 폴더: Langfuse 프롬프트·Skill 연결을 손으로 점검하는 개발용 스크립트를 둡니다. 저장소 루트에서 실행합니다.
- 넣는 것: Langfuse 원격 등록·타임라인을 확인하는 점검 스크립트.
- 넣지 않는 것: 점검 결과 JSON(사용자가 준 경로에 쓰며, 저장소에 둘 때는 `scripts/results/`로 옮김), 서비스 계층 코드(`backend/services/`), 서비스 계층 회귀 테스트(`tests/services/`), 평가셋 실행(`evals/`).
- 담당: 프롬프트

## 파일
- `LANGFUSE.md` — 이 문서
- `langfuse_skill_check.py` — 합성 요청 4건(정격·근거 부재·역할·범위 밖)으로 프롬프트·Skill 버전 연결과 노드 타임라인 점검. `DEMO_MODE=0 uv run python -m scripts.langfuse.langfuse_skill_check <새 결과 JSON>`. 원격 등록은 `--publish`를 명시해야 함
