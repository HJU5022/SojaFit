# mcp_skill

## 역할
- 이 폴더: 가산점용 MCP 서버와 Skill 문서를 둡니다. 에이전트가 서비스 안에서 호출해야 하므로 Dockerfile이 복사하는 `backend/` 아래에 둡니다.
- 넣는 것: RAG 검색을 FastMCP 서버로 노출하는 코드(`mcp_server/`), 도메인 판단 지침 Skill(`skills/SKILL.md`).
- 넣지 않는 것: 판정 임계값과 규칙(`backend/judge/rules/`). SKILL.md에는 LLM 판단 지침만 적고 임계값은 다시 적지 않습니다.
- 담당: 가산을 시작할 때 정합니다.

## 파일
- `mcp_server/server.py` — FastMCP 서버
- `skills/SKILL.md` — S1 정격·시험 조건 해석, S2 회로 연결 설명. 수치 비교·최종 판정·되묻기는 제외

## 안내
둘 다 해야 인정되고, 3차에서 새로 한 통합만 인정됩니다. 2차에서 만든 MCP 서버나 Skill을 그대로 가져온 것은 인정되지 않습니다.

1. 3차 RAG 검색 등을 MCP 서버(FastMCP)로 노출하고, LangGraph 에이전트가 MCP 클라이언트로 호출합니다. (`mcp_server/`)
2. 도메인 판단 규칙을 Skill 문서(`skills/SKILL.md`)로 분리해 에이전트가 쓰고, **같은 평가셋으로 Skill이 있을 때와 없을 때의 점수 차이**를 보입니다.

쓰려면 `uv add mcp`로 `mcp` 패키지를 추가해야 합니다. 그 전에는 `server.py`를 import하지 않습니다.

## 현재 Skill 적용

적용 범위는 [조사](../../docs/skill-feasibility.md)의 S1·S2입니다. Skill에는 상황별 해석 절차를 두고 공통 출력 형식·인용·거절 규칙은 기본 프롬프트에 둡니다. S3~S5는 이번 적용 범위에서 제외합니다.

로컬 본문은 상황 분기를 구체화한 v2 작성안이며 원격 미등록·모델 미검증입니다. Langfuse에서 검증한 Skill v1(sha256 `8a1a9b1e…`)과 구분합니다. 기존 합성4건의 검증 결과는 원격 v1에만 해당하며, 로컬 v2를 적용한 결과가 아닙니다.

- `backend.graph.nodes.generate(state, use_skill=True)`가 고정 경로의 Skill 본문을 기존 시스템 프롬프트 뒤에 추가합니다. 기본값은 `False`입니다. 파일만 만들어 두는 것으로 적용되지 않습니다.
- 생성 결과의 `skill.enabled`는 요청 모드, `skill.applied`는 실제 모델 입력 포함 여부, `skill.sha256`은 포함한 파일의 바이트 해시입니다. 근거가 없으면 모델을 부르지 않아 `applied=False`입니다. 켠 상태에서 파일이 없거나 비어 있으면 오류로 중단합니다.
- 거절 노드는 생성 호출 없이 끝나므로 `skill`을 미적용 상태로 초기화합니다. 이전 턴의 적용 정보를 현재 응답으로 읽지 않습니다.
- 예: 같은 `state`로 `generate(state)`와 `generate(state, use_skill=True)`를 비교합니다. LLM 호출은 두 경우 모두 `backend/services/llm.py`를 거칩니다. 실제 평가 전에 비용·실행 조건을 사전 등록합니다.
- 명시적인 Langfuse 세션에서는 `sojafit/generate`의 고정 버전과 `sojafit/skills/diode-evidence`의 본문·버전·해시를 따로 연결합니다. `DEMO_MODE=0 uv run python -m scripts.langfuse_skill_check <새 결과 JSON>`은 기존 등록 버전을 조회·대조하며, 불일치하면 모델 호출 전에 중단합니다. 원격 반영에는 `--publish`가 필요합니다. 세션 밖은 기존 로컬 파일을 사용합니다.
- 전체 서비스 그래프 조립·MCP 실제 검색 도구와 동결 평가셋 품질 비교는 별도 검증 대상입니다. 합성 자료의 프롬프트/추적 연결 확인을 MCP+Skill 가산 충족이나 품질 개선으로 보고하지 않습니다.
