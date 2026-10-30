# jeongun 작업 기록

## 2026-10-30 폴더 설명 파일 이름을 대문자로
- 한 일: 폴더 설명 파일 22개와 저장소 지도를 대문자 이름으로 바꿨다(`backend/backend.md` → `backend/BACKEND.md`, `SojaFit.md` → `SOJAFIT.md`). 이 파일들을 가리키던 링크·문구와 `<폴더명>.md` 규칙 문구를 고치고, 결정을 ADR 0002로 남겼다. ADR 0001 본문은 그대로 두고 0002를 가리키는 줄만 더했다.
- 바꾼 파일: 이름을 바꾼 23개, `AGENTS.md`, `README.md`, `SPEC.md`, `docs/EVALUATION.md`, `docs/adr/`(0001, 0002, `ADR.md`), 이 파일
- 실행한 명령과 결과: `git mv`로 이름을 바꿔 기록이 이어진다(23개 모두 R로 잡힘). 저장소의 md 44개에서 대소문자까지 구분해 상대 링크 49개를 대조해 깨진 링크 0개. 옛 소문자 이름이 남은 곳은 ADR 0001 본문 1곳(일부러 둠). `uv run --frozen pytest -q`는 2 passed.
- 확인 못 한 것: macOS처럼 대소문자를 구분하지 않는 파일 시스템에서 조원이 이 변경을 받을 때 문제가 없는지는 아직 보지 않았다.
- 다음 할 일: PR을 올리기 전에 정운이 검증한다.

## 2026-10-30 주제서 옮기기와 가산 폴더 정리
- 한 일: 통과한 주제서를 `docs/TOPIC.md`로 옮겼다(본문은 원본과 같음). 가산 중 서비스 안에서 돌아야 하는 MCP·Skill을 `extras/mcp_skill/`에서 `backend/mcp_skill/`로 옮기고, `extras/`는 이미지 밖 작업인 파인튜닝(`extras/finetune/`)만 맡게 했다. GraphRAG와 증분 수집 자동화는 `backend/rag/`에 둔다고 적었다.
- 바꾼 파일: `docs/TOPIC.md`, `backend/mcp_skill/`(옮김), `extras/EXTRAS.md`, `extras/finetune/FINETUNE.md`, `SOJAFIT.md`, `backend/BACKEND.md`, `backend/rag/RAG.md`, `SPEC.md`
- 실행한 명령과 결과: 주제서 본문을 원본과 `diff`해 차이 0줄. `uv run --frozen pytest -q`는 2 passed. 바뀐 문서 15개의 상대 링크 34개 중 깨진 링크 0개.
- 확인 못 한 것: `mcp` 패키지를 아직 넣지 않아 `server.py`는 실행해 보지 않았다. Neo4j와 수집 스케줄러를 어디서 돌릴지는 정하지 않았다.
- 다음 할 일: 조 회의에서 가산 담당과 Neo4j·스케줄러 위치를 정한다.

## 2026-10-30 문서 뼈대 추가
- 한 일: 기능 정본 `SPEC.md` 뼈대(8절), DB 관계도 `db/ERD.md`, 프롬프트 폴더 `backend/prompts/`와 버전 기록 표, 화면 디자인 규칙 `backend/web/DESIGN.md`를 만들었다. 정해진 내용은 주제서·AGENTS·ADR 0001에서 옮기고, 정하지 않은 칸은 `(정할 것)`으로 두었다.
- 바꾼 파일: `SPEC.md`, `SOJAFIT.md`, `db/ERD.md`, `db/DB.md`, `backend/prompts/PROMPTS.md`, `backend/BACKEND.md`, `backend/web/DESIGN.md`, `backend/web/WEB.md`, 이 파일
- 실행한 명령과 결과: 바뀐 문서 8개의 상대 링크 30개를 대조해 깨진 링크 0개. 커밋마다 `git diff --cached --check` 통과. ERD의 라이브러리 표 이름은 `.venv`의 `langgraph-checkpoint-postgres` 3.2.0 소스에서 확인했다.
- 확인 못 한 것: 백로그 보드(GitHub Projects)는 파일이 아니라 만들지 않았다. 데이터시트를 검색 색인용으로 나누는 것이 약관의 "비수정"에 맞는지는 SPEC 6절에 확인할 것으로 남겼다.
- 다음 할 일: 조 회의에서 SPEC의 숫자 성공 기준, 대체 판정 5종의 코드 값과 채점 처리, 그래프 노드를 정한다. 화면 방식(FastAPI 직접 또는 별도 프론트)을 정해 ADR로 남긴다.
