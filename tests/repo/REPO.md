# repo

## 역할
- 이 폴더: 저장소 구조 자체를 검사하는 테스트를 둡니다.
- 넣는 것: 폴더 배치·이름 규칙·폴더 설명 파일을 지키는지 보는 `test_*.py`.
- 넣지 않는 것: 기능 시험(`tests/api/`, `tests/graph/`, `tests/rag/`, `tests/services/`), 평가 시험(`tests/evals/`).
- 담당: 평가·문서

실행: `uv run pytest -q tests/repo`(저장소 루트).

## 파일
- `REPO.md` — 이 문서
- `test_repo_layout.py` — SOJAFIT.md 트리·이름 규칙과 폴더 설명 파일을 지키는지 확인
