# judge

## 역할
- 이 폴더: 회로 속 부품의 역할 규칙을 읽고, 역할에서 대체 조건 기준값을 계산하고, 후보 부품을 판정하는 결정적 코드. 숫자 비교와 단위 비교는 이 폴더에서만 한다. LLM·DB·네트워크를 부르지 않는다.
- 넣는 것: 역할 규칙 파일과 읽기·모양 검사, 기준식 계산, 시험 조건 비교, 판정 5종·찾기 검색 조건·후보 정렬, 공식 PDF 표 인용 검사, 가격 응답의 수량 구간 · 예상 금액 계산(`pricing.py`, `backend/api/prices.py`가 씀).
- 넣지 않는 것: LLM 호출(`backend/services/llm.py`), 검색(`backend/rag/`), 그래프 조립(`backend/multi_agent/`), 단위 환산 함수(`backend/rag/units.py`를 읽기만 함), 도메인 판단 지침 문서(`backend/mcp_skill/skills/SKILL.md`).
- 담당: 에이전트. 규칙 파일은 관련 평가 문항의 정답을 정한 사람이 아닌 다른 조원이 교차 검토한다.

판정 5종(동일품, 사양 동등, 역할상 충분, 불충족, 문서로 확인 안 됨)의 순서와 근거 표기는 [SPEC.md](../../SPEC.md) 3절이고, 규칙 파일 형식은 SPEC.md 5절과 [judge-agent.md](../../docs/specs/judge-agent.md)다. 회로 역할은 판정 읽기 LLM(`backend/multi_agent/agents/judge.py`)이 정하므로 이 폴더에 역할 판별 코드나 조건 파일은 없다. 이 폴더를 부르는 쪽은 `backend/multi_agent/agents/judge.py`(`conditions`, `sheet_conditions`, `verdict`), `backend/multi_agent/supervisor.py`·`backend/multi_agent/agents/docs.py`(`pdf_claims`), `backend/api/conversations.py`·`backend/conversations/models.py`(`conditions`)다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `JUDGE.md` | 이 문서 |
| `pricing.py` | 판매처 조회 응답의 동일 품번·통화·수량 구간을 확인하고 Decimal 예상 금액을 계산. DB·네트워크·저장 없음 |
| `__init__.py` | 패키지 표시(빈 파일) |
| `conditions.py` | 역할 규칙(`rules/roles.yaml`) 읽기·모양 검사, 정해진 문법의 기준식으로 대체 조건 기준값 계산, 인터럽트로 물을 회로 값 목록 |
| `sheet_conditions.py` | 데이터시트 시험 조건 글(기호 = 값, 펄스 폭·파형, 표 제목의 기본 조건)을 읽고 두 조건이 같은지 비교 |
| `verdict.py` | 조건별 비교(통과·실패·확인 안 됨), SPEC 3절 순서의 판정 5종, 찾기 검색 조건, 후보 정렬, 기판 수정 필요 여부. 찾기 조건에는 `when`으로 활성화된 `conditional` 기준도 포함하고, 입력이 없거나 `orig.*`·시험 조건(`at`)에 의존하는 기준은 제외한다. |
| `pdf_claims.py` | 공식 PDF 표 셀에서 인용 문장을 만들고 최종 답의 문장이 일치하는지 검사 |
| `rules/` | 판정 규칙 파일 폴더. `roles.yaml` 하나: 역할마다 알아보는 법, 회로 값, 조건과 기준식, 주의, 출처 |
