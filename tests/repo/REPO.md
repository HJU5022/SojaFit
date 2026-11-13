# repo

## 역할
- 이 폴더: 저장소 구조 자체를 검사하는 테스트.
- 넣는 것: 폴더 배치·이름 규칙·폴더 설명 파일을 지키는지 보는 `test_*.py`.
- 넣지 않는 것: 기능 시험(`tests/api/`, `tests/graph/`, `tests/rag/`, `tests/services/`), 평가 시험(`tests/evals/`).
- 담당: 평가·문서

실행: `uv run pytest -q tests/repo`(저장소 루트).

## 파일
| 파일 | 확인하는 것 |
|---|---|
| `REPO.md` | 이 문서 |
| `test_repo_layout.py` | `SOJAFIT.md` 디렉토리 트리와 실제 파일의 일치, 폴더 설명 파일 이름(`<대문자 폴더명>.md`)과 README.md 위치, 대문자 마크다운 허용 범위, 설명 파일 `## 파일` 절의 자식 누락, 한 폴더 한 종류 파일 규칙 |
