# SojaFit

회로를 읽고 대체 조건을 정해 후보 부품을 판정하는 RAG 에이전트입니다. 첫 범위는 소형 MCU 회로의 다이오드입니다.

사용자가 KiCad 넷리스트와 바꿀 부품을 주면, 부품이 회로에서 맡은 역할을 설명하고, 역할에서 대체 조건을 정하고, 후보 부품마다 데이터시트 근거로 판정한 뒤, 사람이 승인하면 견적서를 저장합니다. 같은 동작은 보장하지 않습니다.

이 문서는 저장소의 지도입니다. 처음 보는 사람은 [README.md](README.md), 기능의 정본은 루트 `SPEC.md`, 폴더 안 파일은 각 폴더의 `README.md`, 바뀐 결정은 [docs/adr/](docs/adr/README.md)를 봅니다.

## 디렉토리 구조

```
SojaFit (proj3-b)
├── README.md  SOJAFIT.md  SPEC.md  AGENTS.md  CLAUDE.md  EVAL_REPORT.md
├── .env.example  .gitignore  .gitattributes  .python-version  Dockerfile  docker-compose.yml  pyproject.toml  uv.lock  pytest.ini
├── .github/          PR 양식, CI(테스트·비밀값 검사)
├── backend/          서비스 코드
│   ├── judge/        회로 역할·대체 조건·판정
│   ├── graph/        LangGraph 그래프
│   ├── prompts/      LLM 프롬프트와 버전 기록
│   ├── rag/          수집·파싱·검색
│   ├── services/     LLM·임베딩 호출, 견적서, 가격·재고
│   ├── web/          화면
│   └── mcp_skill/    MCP 서버와 Skill(가산)
├── data/             코퍼스 목록과 원본 표본(원본 전체는 저장소 밖)
│   ├── corpus/       원본 문서
│   ├── circuits/     평가·시연용 회로
│   └── demo/         데모 모드 응답
├── db/               DB 초기화 SQL
├── evals/            평가셋
├── tests/            테스트
├── scripts/          측정·점검 스크립트
├── docs/             주제서, 계약서, 게이트 증거, 조사 기록
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
| `backend/` | FastAPI 진입점, 로그인, 사용자별 기억, 하위 모듈 | 서비스·운영 | [README.md](backend/README.md) |
| `backend/judge/` | 넷리스트 읽기, 회로 역할, 대체 조건, 판정. 숫자 비교는 여기서만 | 에이전트 | [README.md](backend/judge/README.md) |
| `backend/graph/` | Supervisor, 서브에이전트, 체크포인트, 사람 승인 | 에이전트 | [README.md](backend/graph/README.md) |
| `backend/prompts/` | LLM에 보내는 프롬프트와 버전 기록 | 에이전트 | [README.md](backend/prompts/README.md) |
| `backend/rag/` | 데이터시트 수집, PDF 표 파싱, 단위 환산, 하이브리드 검색, 리랭킹 | 검색·데이터 | [README.md](backend/rag/README.md) |
| `backend/services/` | LLM·임베딩 호출 한 곳, 견적서 저장, 가격·재고 조회 | 서비스·운영 | [README.md](backend/services/README.md) |
| `backend/web/` | 로그인·입력·승인·견적 화면 | 서비스·운영 | [README.md](backend/web/README.md) |
| `backend/mcp_skill/` | 가산: RAG 검색을 노출하는 MCP 서버와 도메인 Skill. 서비스 안에서 돕니다 | 가산을 시작할 때 정함 | [README.md](backend/mcp_skill/README.md) |
| `data/` | manifest와 코퍼스 원본 표본 3건. 원본 PDF·파싱 결과·청크는 저장소 밖 로컬 `SojaFit/corpus/tsc/` | 검색·데이터 | [README.md](data/README.md) |
| `data/corpus/` | 데이터시트·공개 문서 원본 | 검색·데이터 | [README.md](data/corpus/README.md) |
| `data/circuits/` | 평가·시연용 공개 KiCad 회로와 라이선스 | 평가·문서 | [README.md](data/circuits/README.md) |
| `data/demo/` | 키 없는 데모 모드가 재생하는 응답(가공값) | 서비스·운영 | [README.md](data/demo/README.md) |
| `db/` | 초기화 SQL(pgvector·코퍼스·인증), halfvec 수동 전환 SQL, 업무 표 초안 | 서비스·운영 | [README.md](db/README.md) |
| `evals/` | 평가셋, 동결 해시, 평가 실행, 원시 결과 | 평가·문서 | [README.md](evals/README.md) |
| `tests/` | 회귀 테스트, 동결 감시 | 각 모듈 담당 | [README.md](tests/README.md) |
| `scripts/` | 서비스 코드 밖에서 손으로 돌리는 측정·점검 스크립트 | 각 모듈 담당 | [README.md](scripts/README.md) |
| `docs/` | 주제서, 조원 계약서, 게이트 증거, 평가·운영 보충 자료, 임베딩·라이선스 조사 기록 | 평가·문서 | [README.md](docs/README.md) |
| `docs/adr/` | 조 결정 기록 | 결정을 낸 담당 | [README.md](docs/adr/README.md) |
| `docs/specs/` | SPEC에 없는 기능이 생길 때 쓰는 작업서 | 그 기능의 담당 | [README.md](docs/specs/README.md) |
| `docs/deliverables/` | 제출물 | 평가·문서 | [README.md](docs/deliverables/README.md) |
| `docs/worklog/` | 조원별 작업 기록 | 각자 자기 파일 | [README.md](docs/worklog/README.md) |
| `extras/` | 가산 중 이미지에 들어가지 않는 작업(학습) | 가산을 시작할 때 정함 | [README.md](extras/README.md) |
| `extras/finetune/` | 가산: 파인튜닝 학습 코드와 비교 결과 | 가산을 시작할 때 정함 | [README.md](extras/finetune/README.md) |

담당은 가이드의 역할 4개(검색·데이터, 에이전트, 서비스·운영, 평가·문서)입니다. 사람 배정은 [README.md](README.md) 조원 표에 있습니다.

## 루트 파일

| 파일 | 하는 일 |
|---|---|
| `README.md` | 대표 문서. 한 줄 정의, 팀 정보와 배포 주소, 조원표, 실행 방법과 데모 모드, 일정, 작업 흐름 |
| `SOJAFIT.md` | 이 문서. 저장소 지도 |
| `SPEC.md` | 기능의 정본. 범위, 흐름, 대체 판정 5종, 계약, 규칙 파일, 코퍼스 경계, 데모 모드, 기능별 AC |
| `AGENTS.md` | AI 코딩 에이전트 지침과 조 팀 규칙 |
| `CLAUDE.md` | Claude Code가 읽는 지침. AGENTS.md를 따름 |
| `EVAL_REPORT.md` | 개선 전후 지표, 판정 기준, 실패 분석, 재현 명령 |
| `.env.example` | 필요한 환경변수 이름(값 없음) |
| `.gitignore` | 커밋하지 않을 파일(`.env`, 캐시, 로그 등) |
| `.python-version` | uv가 쓰는 파이썬 버전(3.12) |
| `.gitattributes` | 해시를 기록한 회로·PDF를 줄바꿈 변환 없이 받게 함 |
| `Dockerfile`, `docker-compose.yml` | `docker compose up` 한 줄 실행, 키 없는 데모 모드 |
| `pyproject.toml`, `uv.lock`, `pytest.ini` | 의존성과 테스트 설정 |

## 이름 규칙

- 폴더 설명은 폴더마다 `README.md` 하나에 적습니다(예: `backend/README.md`, [ADR 0011](docs/adr/0011-폴더-설명-파일은-readme로-쓴다.md)). 역할, 넣는 것, 넣지 않는 것, 담당, 파일을 적습니다. 두 단계까지만 두고, 더 깊은 폴더는 위 폴더의 `.md`에 한 줄로 적습니다.
- 루트 대표 문서(`README.md`, `SOJAFIT.md`, `SPEC.md`, `AGENTS.md`, `CLAUDE.md`, `EVAL_REPORT.md`)와 폴더 설명 파일만 대문자로 씁니다. 그 밖의 파일 이름은 대소문자를 가리지 않습니다.
- 원본·결과물만 담는 폴더(`evals/results/`, 생기면 `tests/fixtures/`, `docs/deliverables/langfuse/`)와 `.github/`에는 폴더 설명을 두지 않습니다.
- 새 폴더를 만드는 PR은 그 폴더의 `README.md`와 이 문서의 표 한 줄을 같이 넣습니다.
- 결정 기록은 `docs/adr/NNNN-한국어-제목.md`, 기능 작업서는 `docs/specs/<english-kebab>.md`입니다.
- 강사 스캐폴드의 고정 경로(`backend/` 패키지, 루트 `tests/`, `evals/`, `db/`, 루트 빌드 파일)는 옮기지 않습니다.

## 처음 할 일

1. `cp .env.example .env` 후 `docker compose up`으로 `/health`가 뜨는지 확인합니다.
2. 위 폴더 표에서 손댈 폴더를 고르고 그 폴더의 `README.md`부터 읽습니다.
