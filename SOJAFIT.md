# SojaFit

회로를 읽고 대체 조건을 정해 후보 부품을 판정하는 RAG 에이전트입니다. 첫 범위는 소형 MCU 회로의 다이오드입니다.

사용자가 KiCad 넷리스트와 바꿀 부품을 주면, 부품이 회로에서 맡은 역할을 설명하고, 역할에서 대체 조건을 정하고, 후보 부품마다 데이터시트 근거로 판정한 뒤, 사람이 승인하면 견적서를 저장합니다. 같은 동작은 보장하지 않습니다.

이 문서는 저장소의 지도입니다. 처음 보는 사람은 [README.md](README.md), 기능의 정본은 루트 `SPEC.md`, 폴더 안 파일은 각 폴더의 `<대문자 폴더명>.md`, 바뀐 결정은 [docs/adr/](docs/adr/ADR.md)를 봅니다.

## 디렉토리 구조

```
SojaFit (proj3-b)
├── README.md  SOJAFIT.md  SPEC.md  AGENTS.md  CLAUDE.md  EVAL_REPORT.md
├── .env.example  Dockerfile  docker-compose.yml  pyproject.toml  uv.lock  pytest.ini
├── .github/          PR 양식, CI(테스트·비밀값 검사)
├── backend/          서비스 코드
│   ├── judge/        회로 역할·대체 조건·판정
│   ├── graph/        LangGraph 그래프
│   ├── prompts/      LLM 프롬프트와 버전 기록
│   ├── rag/          수집·파싱·검색
│   ├── services/     LLM·임베딩 호출, 견적서, 가격·재고
│   ├── web/          화면
│   └── mcp_skill/    MCP 서버와 Skill(가산)
├── data/             코퍼스와 목록
│   ├── corpus/       원본 문서
│   ├── circuits/     평가·시연용 회로
│   └── demo/         데모 모드 응답
├── db/               DB 초기화 SQL
├── evals/            평가셋
├── tests/            테스트
├── docs/             주제서, 계약서, 게이트 증거
│   ├── adr/          조 결정 기록
│   ├── specs/        SPEC 밖 기능 작업서
│   ├── deliverables/ 제출물
│   └── worklog/      조원별 작업 기록
└── extras/           이미지에 들어가지 않는 가산 작업
    └── finetune/     파인튜닝(가산)
```

## 폴더마다 하는 일

| 폴더 | 하는 일 | 담당 | 설명 |
|---|---|---|---|
| `backend/` | FastAPI 진입점, 로그인, 사용자별 기억, 하위 모듈 | 서비스·운영 | [BACKEND.md](backend/BACKEND.md) |
| `backend/judge/` | 넷리스트 읽기, 회로 역할, 대체 조건, 판정. 숫자 비교는 여기서만 | 에이전트 | [JUDGE.md](backend/judge/JUDGE.md) |
| `backend/graph/` | Supervisor, 서브에이전트, 체크포인트, 사람 승인 | 에이전트 | [GRAPH.md](backend/graph/GRAPH.md) |
| `backend/prompts/` | LLM에 보내는 프롬프트와 버전 기록 | 에이전트 | [PROMPTS.md](backend/prompts/PROMPTS.md) |
| `backend/rag/` | 데이터시트 수집, PDF 표 파싱, 단위 환산, 하이브리드 검색, 리랭킹 | 검색·데이터 | [RAG.md](backend/rag/RAG.md) |
| `backend/services/` | LLM·임베딩 호출 한 곳, 견적서 저장, 가격·재고 조회 | 서비스·운영 | [SERVICES.md](backend/services/SERVICES.md) |
| `backend/web/` | 로그인·입력·승인·견적 화면 | 서비스·운영 | [WEB.md](backend/web/WEB.md) |
| `backend/mcp_skill/` | 가산: RAG 검색을 노출하는 MCP 서버와 도메인 Skill. 서비스 안에서 돕니다 | 가산을 시작할 때 정함 | [MCP_SKILL.md](backend/mcp_skill/MCP_SKILL.md) |
| `data/` | 코퍼스 스냅샷과 manifest·청크·파라미터 목록 | 검색·데이터 | [DATA.md](data/DATA.md) |
| `data/corpus/` | 데이터시트·공개 문서 원본 | 검색·데이터 | [CORPUS.md](data/corpus/CORPUS.md) |
| `data/circuits/` | 평가·시연용 공개 KiCad 회로와 라이선스 | 평가·문서 | [CIRCUITS.md](data/circuits/CIRCUITS.md) |
| `data/demo/` | 키 없는 데모 모드가 재생하는 응답(가공값) | 서비스·운영 | [DEMO.md](data/demo/DEMO.md) |
| `db/` | 스키마, 스냅샷 적재, 인덱스, 데모 계정 | 서비스·운영 | [DB.md](db/DB.md) |
| `evals/` | 평가셋, 동결 해시, 평가 실행, 원시 결과 | 평가·문서 | [EVALS.md](evals/EVALS.md) |
| `tests/` | 회귀 테스트, 동결 감시 | 각 모듈 담당 | [TESTS.md](tests/TESTS.md) |
| `docs/` | 주제서, 조원 계약서, 게이트 증거 | 평가·문서 | [DOCS.md](docs/DOCS.md) |
| `docs/adr/` | 조 결정 기록 | 결정을 낸 담당 | [ADR.md](docs/adr/ADR.md) |
| `docs/specs/` | SPEC에 없는 기능이 생길 때 쓰는 작업서 | 그 기능의 담당 | [SPECS.md](docs/specs/SPECS.md) |
| `docs/deliverables/` | 제출물 | 평가·문서 | [DELIVERABLES.md](docs/deliverables/DELIVERABLES.md) |
| `docs/worklog/` | 조원별 작업 기록 | 각자 자기 파일 | [WORKLOG.md](docs/worklog/WORKLOG.md) |
| `extras/` | 가산 중 이미지에 들어가지 않는 작업(학습) | 가산을 시작할 때 정함 | [EXTRAS.md](extras/EXTRAS.md) |
| `extras/finetune/` | 가산: 파인튜닝 학습 코드와 비교 결과 | 가산을 시작할 때 정함 | [FINETUNE.md](extras/finetune/FINETUNE.md) |

담당은 가이드의 역할 4개(검색·데이터, 에이전트, 서비스·운영, 평가·문서)입니다. 사람 배정은 [docs/조원-계약서.md](docs/조원-계약서.md)에 적습니다.

## 루트 파일

| 파일 | 하는 일 |
|---|---|
| `README.md` | 대표 문서. 한 줄 정의, 지표, 실행 방법, 데모 모드, 배포 주소, 조원표, 작업 흐름 |
| `SOJAFIT.md` | 이 문서. 저장소 지도 |
| `SPEC.md` | 기능의 정본. 범위, 흐름, 대체 판정 5종, 계약, 규칙 파일, 코퍼스 경계, 데모 모드, 기능별 AC |
| `AGENTS.md` | AI 코딩 에이전트 지침과 조 팀 규칙 |
| `CLAUDE.md` | Claude Code가 읽는 지침. AGENTS.md를 따름 |
| `EVAL_REPORT.md` | 개선 전후 지표, 판정 기준, 실패 분석, 재현 명령 |
| `.env.example` | 필요한 환경변수 이름(값 없음) |
| `.gitattributes` | 해시를 기록한 회로·PDF를 줄바꿈 변환 없이 받게 함 |
| `Dockerfile`, `docker-compose.yml` | `docker compose up` 한 줄 실행, 키 없는 데모 모드 |
| `pyproject.toml`, `uv.lock`, `pytest.ini` | 의존성과 테스트 설정 |

## 이름 규칙

- 폴더 설명은 폴더마다 `<대문자 폴더명>.md` 하나에 적습니다(예: `backend/BACKEND.md`). 역할, 넣는 것, 넣지 않는 것, 담당, 파일을 적습니다. 두 단계까지만 두고, 더 깊은 폴더는 위 폴더의 `.md`에 한 줄로 적습니다.
- 루트 대표 문서(`README.md`, `SOJAFIT.md`, `SPEC.md`, `AGENTS.md`, `CLAUDE.md`, `EVAL_REPORT.md`)와 폴더 설명 파일만 대문자로 씁니다. 그 밖의 파일 이름은 대소문자를 가리지 않습니다.
- 원본·결과물만 담는 폴더(`evals/results/`, `tests/fixtures/`, `docs/deliverables/langfuse/`)와 `.github/`에는 폴더 설명을 두지 않습니다.
- 새 폴더를 만드는 PR은 그 폴더의 `.md`와 이 문서의 표 한 줄을 같이 넣습니다.
- 결정 기록은 `docs/adr/NNNN-한국어-제목.md`, 기능 작업서는 `docs/specs/<english-kebab>.md`입니다.
- 강사 스캐폴드의 고정 경로(`backend/` 패키지, 루트 `tests/`, `evals/`, `db/`, 루트 빌드 파일)는 옮기지 않습니다.

## 처음 할 일 (강사 스캐폴드 안내)

1. README 조원 소개 표에 자기 행을 추가합니다(브랜치 → PR → 리뷰 → merge). 첫 PR이 협업 흐름 연습입니다.
2. `cp .env.example .env` 후 `docker compose up`으로 `/health`가 뜨는지 확인합니다.
3. D0(10/30)에 빈 FastAPI를 Cloud Run에 올려 배포 주소를 확보합니다.
4. 평가셋 v1 30건을 만듭니다(11/3 동결).
