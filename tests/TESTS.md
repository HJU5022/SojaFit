# tests

## 역할
- 이 폴더: PR마다 CI가 돌리는 회귀 테스트를 둡니다. `pytest.ini`가 이 폴더를 가리키므로 루트 직속에 평면으로 둡니다.
- 넣는 것: 모듈별 테스트(`test_<모듈>.py`), 동결 감시, 핵심 질문이 근거를 붙여 답하는지 보는 평가 회귀 테스트, 단위 테스트용 가공 회로(`fixtures/`).
- 넣지 않는 것: 평가셋 전체 실행(`evals/`). GitHub Actions 무료 한도가 있어 PR마다 평가 전체를 돌리지 않고 샘플만 돌립니다.
- 담당: 각 모듈의 담당 (`test_frozen_evals.py`는 평가·문서)

## 파일
- `test_health.py` — `/health` 응답 확인
- `test_frozen_evals.py` — `evals/FROZEN.json`에 기록된 파일의 해시가 바뀌지 않았는지 확인. `FROZEN.json`이 없으면 검사하지 않고 통과합니다
- `test_llm.py` — API 호출 없이 mock client로 중앙 임베딩 호출의 벡터·사용량·provider metadata 반환 계약 확인
- `test_rag_chunk.py` — 표 카드 규칙(합친 칸 채우기, 머리 행 두 줄 잇기, 빈 표)과 문서 키
