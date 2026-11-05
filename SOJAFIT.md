# SojaFit

회로를 읽고 대체 조건을 정해 후보 부품을 판정하는 RAG 에이전트입니다. 첫 범위는 소형 MCU 회로의 다이오드입니다.

사용자가 KiCad 넷리스트와 바꿀 부품을 주면, 부품이 회로에서 맡은 역할을 설명하고, 역할에서 대체 조건을 정하고, 후보 부품마다 데이터시트 근거로 판정한 뒤, 사람이 승인하면 견적서를 저장합니다. 같은 동작은 보장하지 않습니다.

**이 문서는 폴더와 파일 위치의 정본입니다.** 파일을 만들거나 옮기기 전에 아래 트리에서 `<-` 설명이 맞는 자리를 찾습니다. 처음 보는 사람은 [README.md](README.md), 기능의 정본은 루트 `SPEC.md`, 폴더의 넣는 것·넣지 않는 것은 각 폴더의 `<대문자 폴더명>.md`, 바뀐 결정은 [docs/adr/](docs/adr/ADR.md)를 봅니다.

## 디렉토리 구조

`(고정)`은 강사 스캐폴드·과제 가이드·코드가 경로를 정해 옮기지 않는 것, `(예정)`은 문서가 만들기로 정했지만 아직 없는 파일·폴더(`후보 이름`은 SPEC이 이름을 정하면 바꾸는 것), `(지금은 .gitkeep)`은 자리만 만들어 둔 빈 폴더입니다.

```
SojaFit (proj3-b)
├── README.md               <- 대표 문서: 한 줄 정의, 팀·배포 주소, 조원표, 실행 방법과 데모 모드, 일정, 협업 규칙
├── SOJAFIT.md              <- 이 문서: 디렉토리 트리(파일 위치의 정본)와 이름 규칙
├── SPEC.md                 <- 기능의 정본: 범위, 흐름, 대체 판정 5종, 계약, 규칙 파일, 코퍼스 경계, 데모 모드, AC
├── AGENTS.md               <- AI 코딩 에이전트 지침과 조 팀 규칙
├── CLAUDE.md               <- Claude Code 진입점. AGENTS.md를 불러옴
├── EVAL_REPORT.md          <- 개선 전후 지표, 판정 기준, 실패 분석, 재현 명령 (고정)
├── .env.example            <- 필요한 환경변수 이름과 가짜 값(실제 키는 .env에만)
├── .gitignore              <- 커밋하지 않을 파일(.env, 캐시, graphify-out/ 등)
├── .gitattributes          <- 해시를 기록한 회로·PDF를 줄바꿈 변환 없이 받게 함
├── .python-version         <- uv가 쓰는 파이썬 버전(3.12)
├── Dockerfile              <- API 이미지. backend/와 data/만 복사 (고정)
├── docker-compose.yml      <- api + pgvector DB 한 줄 실행, 키 없는 데모 모드 (고정)
├── pyproject.toml          <- uv 의존성 (고정)
├── uv.lock                 <- 의존성 고정 버전. pyproject.toml과 같은 커밋에 넣음
├── pytest.ini              <- 테스트 경로(tests/)와 설정
│
├── .github/                <- GitHub 설정(설명 파일 없음)
│   ├── PULL_REQUEST_TEMPLATE.md  <- PR 본문 양식
│   └── workflows/
│       ├── ci.yml          <- PR마다 테스트(격리한 인증 시험 DB 포함)
│       └── secret-scan.yml <- gitleaks 키 노출 검사
│
├── backend/                <- 서비스 코드 전부. Dockerfile이 이미지에 복사 (고정)
│   ├── BACKEND.md          <- 폴더 설명
│   ├── __init__.py         <- 패키지 표시
│   ├── main.py             <- FastAPI 진입점: /health, 로그인·me·로그아웃, 관리자 계정 API (고정: Dockerfile이 실행)
│   ├── auth.py             <- scrypt 비밀번호, DB 세션, 로그인 잠금, 관리자 계정 관리, 계정 생성 CLI
│   ├── settings.py         <- 환경변수를 한곳에서 읽는 설정 (예정)
│   ├── schemas.py          <- 모듈 사이에 주고받는 데이터 형식 (예정)
│   ├── graph/              <- LangGraph 그래프: 상태, 노드, 조립, 사용자별 기억
│   │   ├── GRAPH.md        <- 폴더 설명. Supervisor·체크포인트·승인 단계가 들어올 자리
│   │   ├── __init__.py     <- 패키지 표시
│   │   ├── state.py        <- 질문 하나가 노드를 지나는 동안 쓰는 공용 메모장(AgentState)
│   │   ├── supervisor.py   <- Supervisor V0 공통 입출력·상태 라우팅 의미 계약(그래프 미연결)
│   │   ├── nodes.py        <- 노드 7개: 입력 읽기, 라우팅, 검색, 채점, 재작성, 생성, 거절
│   │   ├── mcp_retriever.py  <- PR #44 MCP 응답을 검증하고 stdio 세션을 재사용하는 LangGraph 검색기
│   │   ├── build.py        <- 노드를 잇고 갈림길을 정해 그래프 앱을 만듦
│   │   └── memory.py       <- 사용자별 장기 기억(Store) namespace 규칙. 아직 부르는 곳 없음
│   ├── judge/              <- 회로 역할·대체 조건·판정의 결정적 코드. 숫자·단위 비교는 여기서만
│   │   ├── JUDGE.md        <- 폴더 설명
│   │   ├── netlist.py      <- 넷리스트에서 대상 부품 주변 연결 읽기 (예정, 후보 이름)
│   │   ├── roles.py        <- 회로에서 부품의 역할 정하기 (예정, 후보 이름)
│   │   ├── conditions.py   <- 역할에서 대체 조건 도출 (예정, 후보 이름)
│   │   ├── verdict.py      <- 후보마다 판정 5종 내기 (예정, 후보 이름)
│   │   └── rules/          <- 판정 규칙 파일. 형식은 SPEC 5절에서 정함(지금은 .gitkeep)
│   │       ├── roles.yaml  <- 역할 규칙 (예정, 후보 이름)
│   │       └── conditions.yaml  <- 대체 조건 규칙 (예정, 후보 이름)
│   ├── prompts/            <- 노드가 LLM에 보내는 프롬프트 원문과 버전 기록
│   │   ├── PROMPTS.md      <- 폴더 설명과 프롬프트 버전 기록 표
│   │   ├── supervisor_v0.md  <- Supervisor V0 질문 분류·근거·다음 경로 시스템 프롬프트
│   │   ├── route.md        <- 질문 종류 분류(라우팅 노드)
│   │   ├── grade.md        <- 검색 청크 채점(채점 노드)
│   │   ├── rewrite.md      <- 검색어 다시 쓰기(재작성 노드)
│   │   ├── generate.md     <- 통과 청크만 근거로 답하기(생성 노드)
│   │   └── tool_use.md     <- MCP 도구 선택·결과 해석. 아직 코드가 읽지 않음
│   ├── rag/                <- 하이브리드 검색(서버)과 벡터 저장 형식. 오프라인 데이터 도구는 pipeline/
│   │   ├── RAG.md          <- 폴더 설명과 CLI 실행 순서
│   │   ├── __init__.py     <- 패키지 표시
│   │   ├── retrieve.py     <- BM25 + 벡터를 RRF로 합친 하이브리드 검색, 품번 필터 (서버 import)
│   │   ├── storage.py      <- 벡터 열 형식(vector/halfvec) 결정과 DB 용량·형식 비교 CLI
│   │   ├── units.py        <- 표 값의 단위 환산. judge가 읽기만 함(SPEC 3절) (예정)
│   │   └── pipeline/       <- 오프라인 데이터 도구. python -m backend.rag.pipeline.<모듈>로 실행, 서버는 import 안 함
│   │       ├── __init__.py <- 패키지 표시
│   │       ├── collect.py  <- TSC 목록 xlsx를 합치고 데이터시트 PDF를 받음
│   │       ├── parse.py    <- PDF를 Docling으로 파싱하고 표 숫자를 pdfplumber로 대조
│   │       ├── chunk.py    <- 파싱 결과를 검색 청크(표지·글·표 행)와 manifest로 만듦
│   │       ├── ingest.py   <- manifest·청크·임베딩을 DB에 적재, 벡터 캐시 지원
│   │       └── subset.py   <- 용량 예산에 맞춰 일부 분류 문서만 뽑음
│   ├── services/           <- 외부 호출을 모으는 한 곳: LLM·임베딩, Langfuse, 견적·가격
│   │   ├── SERVICES.md     <- 폴더 설명
│   │   ├── __init__.py     <- 패키지 표시
│   │   ├── llm.py          <- LLM·임베딩 호출의 유일한 입구: 평가 예산, 재시도 상한(데모 응답 재생은 아직 없음)
│   │   ├── langfuse_prompts.py  <- Langfuse 프롬프트 등록, 고정 버전 검증, 노드 추적
│   │   ├── quote.py        <- 사람이 승인한 견적서 저장(SPEC 8.4) (예정)
│   │   └── mouser.py       <- Mouser 가격·재고 조회, 응답은 저장하지 않음(ADR 0009, 확장 단계) (예정)
│   ├── web/                <- 같은 출처 로그인·질문 화면과 앞으로의 입력·승인·견적 화면
│   │   ├── WEB.md          <- 폴더 설명
│   │   ├── design.md       <- 화면 디자인 규칙 초안
│   │   ├── templates/      <- 화면 HTML 템플릿
│   │   │   └── login.html  <- 같은 출처 로그인·비저장 질문·로그아웃 화면
│   │   └── static/         <- 화면 정적 파일(지금은 .gitkeep)
│   └── mcp_skill/          <- 가산: RAG 검색을 노출하는 MCP 서버와 도메인 Skill
│       ├── MCP_SKILL.md    <- 폴더 설명
│       ├── mcp_server/
│       │   └── server.py   <- FastMCP 서버 자리표시자(example_tool만 있음)
│       └── skills/
│           └── SKILL.md    <- 다이오드 정격 해석·회로 연결 설명 지침. use_skill을 켠 생성 호출만 시스템 프롬프트에 붙임 (고정: 코드가 경로를 읽음)
│
├── data/                   <- 서비스·평가가 읽는 고정 데이터. Dockerfile이 이미지에 복사 (고정)
│   ├── DATA.md             <- 폴더 설명과 manifest 형식
│   ├── manifest.jsonl      <- 코퍼스 문서 목록 1,360줄(문서 단위: id, 판본, 출처, sha256)
│   ├── corpus/             <- 코퍼스 원본 문서. 출처별 하위 폴더, 원본은 고치지 않음
│   │   ├── CORPUS.md       <- 폴더 설명, 출처별 폴더와 재배포 조건
│   │   ├── tsc/            <- TSC 다이오드 데이터시트 원본 표본 3건(PDF). 전체 1,360건은 저장소 밖 ../corpus/tsc/pdf/
│   │   ├── public/         <- KiCad 문서·Wikipedia·SparkFun 등 공개 라이선스 문서(지금은 .gitkeep)
│   │   └── injection_tests/  <- 간접 인젝션 시험 문서 3건 이상(지금은 .gitkeep)
│   ├── circuits/           <- 평가·시연용 공개 KiCad 회로와 라이선스
│   │   ├── CIRCUITS.md     <- 폴더 설명, 회로별 원 저장소·커밋·라이선스 표
│   │   └── collected/      <- 받은 회로(received-*/)와 공개 표본(samples/*/): original/(원본), converted/(넷리스트·connections.json)
│   └── demo/               <- 키 없는 데모 모드가 재생할 응답(파일 이름은 데모 시나리오를 정할 때 정함)
│       └── DEMO.md         <- 폴더 설명
│
├── db/                     <- Postgres가 첫 기동 때 바로 아래 .sql만 이름순으로 자동 실행 (고정: compose가 ./db를 초기화 폴더로 붙임)
│   ├── DB.md               <- 폴더 설명, 실행 순서, 기존 DB 점검 절차
│   ├── 000_init.sql        <- pgvector 확장
│   ├── 002_rag_corpus.sql  <- 코퍼스 문서·청크·벡터 표
│   ├── 003_auth.sql        <- 사용자·세션·로그인 시도 표
│   ├── 004_create_business_tables.sql  <- 업무 표(회로·판정·견적). 확정되면 manual/의 초안을 옮김 (예정)
│   ├── 005_auth_attempt_window.sql  <- 로그인 시도 창 시작 시각 열
│   ├── 006_user_roles.sql  <- 사용자 역할(admin/user) 열
│   ├── 007_demo_accounts.sql  <- 로컬 Compose 데모 계정(.env의 이메일·scrypt 해시)
│   ├── 008_multi_dim_embeddings.sql  <- 임베딩 열을 차원 없는 halfvec으로(모델별 차원 공존)
│   ├── 009_chunk_embedding_bits.sql  <- voyage 임베딩의 1비트 코드 표(dense 1단계 Hamming 후보용)
│   ├── manual/             <- 자동 실행하지 않는 SQL. 손으로 실행
│   │   ├── MANUAL.md       <- 폴더 설명
│   │   ├── 004_create_business_tables.sql.draft  <- 업무 표 마이그레이션 초안
│   │   └── halfvec.sql.manual  <- 복제 DB에서 vector→halfvec 전환
│   └── schema/             <- 스키마 설명 문서
│       ├── SCHEMA.md       <- 폴더 설명
│       ├── erd.md          <- DB ERD
│       └── table-definition.md  <- 업무 표(회로·판정·견적) 설계 초안
│
├── evals/                  <- 평가셋과 평가 실행. 루트에는 동결 평가셋만 둠 (고정: 루트의 평가셋·FROZEN.json)
│   ├── EVALS.md            <- 폴더 설명
│   ├── dataset_v1.jsonl    <- 동결 평가셋 v1: 50건(관련 25·비관련 25), 2026-11-02 (고정)
│   ├── dataset_v2.jsonl    <- 동결 평가셋 v2: 70건(v1 50 + 후보 찾기 20, 관련 35·비관련 35), question_type 칸, 2026-11-03 (고정)
│   ├── FROZEN.json         <- 동결 파일별 sha256·건수. 테스트가 이 이름을 읽음 (고정)
│   ├── exclusions.json     <- 동결 뒤 코퍼스가 바뀌어 지표에서만 뺄 문항 id와 사유(과제 가이드) (예정)
│   ├── inputs/             <- 동결 평가셋에서 만든 측정 입력(qrels·고정 질의). 측정 전에 커밋
│   │   ├── INPUTS.md       <- 폴더 설명
│   │   ├── qrels_v2_pages.json  <- v2 채점 19문항의 필수 근거 페이지 36개(회수 불가 2쪽 표시, 사전 등록 #24)
│   │   ├── rewrite_q3_v2.json  <- 같은 19문항의 고정 재작성 질의 Q3(서비스 rewrite() 출력 그대로)
│   │   └── layers/         <- 검색 조합 층별 재측정(11-03)의 고정 입력. 깊은 폴더라 설명은 INPUTS.md에
│   │       ├── parts.json  <- 0층에서 고정한 질문 줄·품번·비교 여부
│   │       ├── queries.jsonl  <- LLM이 한 번 만들어 고정한 질의 Q3~Q5
│   │       ├── queries_check.json  <- 고정 질의의 자동 확인(품번 남음·없던 숫자) 걸린 건
│   │       └── query_texts.jsonl  <- 임베딩에 보낸 질의 글 전체(sha·본문)
│   ├── guides/             <- 평가 기준 문서
│   │   ├── GUIDES.md       <- 폴더 설명
│   │   ├── dataset-guide.md  <- 평가셋 필드·관련/비관련 분류·동결·판정 방식의 정본
│   │   ├── preregister.md  <- 실험 사전 등록: 바꾸기 전에 바꿀 것과 기대 지표를 적음
│   │   └── supervisor-prompt-v0.md  <- 수퍼바이저 V0 세 후보의 오프라인 준비·live 승인 gate·실행·집계 순서
│   ├── runners/            <- 평가 실행기. python -m evals.runners.<이름>으로 실행
│   │   ├── RUNNERS.md      <- 폴더 설명과 실행 명령
│   │   ├── run_retrieval.py  <- 관련 문항의 검색 지표(문서 Recall@k·MRR·Page Hit@k)를 재서 results/retrieval/에 저장
│   │   ├── run_retrieval_d3.py  <- D3 공식 검색 측정(v2 페이지 단위 qrels, 한 번에 한 조건 E1~E8·필터 끔 재측정·no_result·탐색 격자)
│   │   ├── run_retrieval_r1.py  <- R1 검색 측정(84문항, 임베딩×필터×질의×리랭커 264칸을 dev 세트에서 고르고 test 세트에서 한 번 비교)
│   │   ├── run_retrieval_service.py  <- 서비스 경로 재측정(실제 retrieve()로 R1 84·v2 19문항 지표, R1 1위 칸과 상위 5개 대조, 시간·비용; 사전 등록 #26)
│   │   ├── run_graph.py    <- 평가셋 문항을 그래프로 끝까지 돌려 Langfuse에 트레이스·실행 점수를 남김
│   │   ├── run_supervisor_models.py  <- 수퍼바이저 5종 평가 계획·호출·집계와 provider 검증
│   │   ├── run_supervisor_jev.py  <- Jev Decisions API 평가 계획·호출·집계
│   │   ├── report_supervisor_stage3.py  <- 1~3차 원시 행의 API 없는 비교·3차 재집계
│   │   ├── supervisor_prompt_v0_common.py  <- 수퍼바이저 V0 표본 무결성·입력 격리·공통 채점
│   │   ├── run_supervisor_prompt_v0.py  <- Luna·Haiku 수퍼바이저 V0 오프라인 plan·명시적 live 실행
│   │   ├── run_supervisor_prompt_v0_jev.py  <- Jev Decisions 수퍼바이저 V0 오프라인 plan·typed answer 정규화·상한 실행
│   │   ├── compare_supervisor_prompt_v0.py  <- 수퍼바이저 V0 세 후보의 hash·case 일치 확인과 공통 지표 집계
│   │   ├── import_supervisor_prompt_v0_langfuse.py  <- 완료된 V0 결과를 모델 재호출 없이 Langfuse Dataset·Experiment로 가져오기
│   │   ├── score_answer.py <- 평가셋 문항과 그래프 실행 상태를 대조해 답변·거절 5지표를 규칙 기반으로 채점
│   │   ├── run_skill_pair.py  <- 같은 검색 상태에서 Skill 유무에 따른 답 차이를 순차 비교(사전 등록 #17)
│   │   ├── freeze.py       <- 평가셋 sha256·건수를 FROZEN.json에 기록, --check로 검사
│   │   ├── benchmark_embeddings.py  <- 프록시 표본으로 임베딩 후보의 Recall@5·MRR·지연 예비 측정
│   │   ├── embed_cards.py  <- 임베딩 격자 본평가(#16)의 카드 적재와 모델별 카드 임베딩(실험 DB, 컨테이너)
│   │   ├── run_embedding_grid.py  <- 임베딩 6종 × 검색 방식 × 리랭커 78칸 측정(#16, 컨테이너)
│   │   ├── check_retrieval_db.py  <- 층별 재측정 0층: Supabase 카드·벡터·검색 결과를 로컬과 대조(읽기만)
│   │   ├── run_retrieval_layers.py  <- 검색 조합 층별 재측정 1~4층(질의 글·토큰화·임베딩·리랭커, 11-03)
│   │   └── report_retrieval_layers.py  <- 층별 재측정의 사전 등록 비교값을 결과 파일에서 뽑아 정리
│   ├── docker/             <- 평가 실험용 컨테이너 이미지 정의
│   │   ├── DOCKER.md       <- 폴더 설명
│   │   ├── Dockerfile.gpu_embed  <- 원격 GPU에서 로컬 임베딩 모델을 돌리는 이미지(sojafit-emb)
│   │   └── Dockerfile.embedding_grid  <- 임베딩 격자 본평가 실행 이미지(gpu_embed에 DB·BM25·Voyage 패키지를 더함)
│   ├── samples/            <- 동결하지 않은 프록시 표본
│   │   ├── SAMPLES.md      <- 폴더 설명
│   │   ├── embedding_sample_v0.jsonl  <- 임베딩 후보를 거르는 표본(30청크·18질의)
│   │   ├── retrieval_r1.jsonl  <- 문서 구조로 정답 페이지를 정한 검색 표본 84문항(dev 세트 46·test 세트 38, 사전 등록 #25)
│   │   ├── retrieval_r1_rewrite_q3.json  <- 같은 84문항의 고정 재작성 질의 Q3(서비스 rewrite() 출력 그대로)
│   │   ├── supervisor_prompt_v0.jsonl  <- 수퍼바이저 V0 세 후보의 상태 전이 비교 표본 13건(v1·v2와 별도)
│   │   └── supervisor_prompt_v0_frozen.json  <- V0 13건의 sha256·건수 무결성 기록
│   ├── drafts/             <- 동결 전 평가셋 초안과 검수 기록(실행·동결 금지, 이력 보존)
│   │   ├── DRAFTS.md       <- 폴더 설명
│   │   ├── sets/           <- 초안 문항
│   │   │   ├── draft_30.jsonl  <- 난이도별 30건 첫 초안
│   │   │   ├── draft_50.jsonl  <- 50건 검수 초안. 고정 키만 dataset_v1.jsonl로 옮겨 동결
│   │   │   └── draft_v2add_20.jsonl  <- v2 추가 후보 찾기 20건 초안과 사람 판정 기록. 고정 키만 dataset_v2.jsonl로 옮겨 동결
│   │   └── reviews/        <- 초안 검토표
│   │       ├── draft_30_review.md  <- 30건 초안의 질문·가정·예상 답 검수 목록
│   │       ├── draft_50_review.md  <- 50건 검토표와 합의 기록
│   │       ├── draft_v2add_20_review.md  <- 20건 검토표와 1·2차 사람 판정 기록
│   │       └── second_pass_50_review.md  <- 11-02 동결 전 보조 검증 기록
│   └── results/            <- 평가 원시 결과. <무엇>_<날짜>.json을 주제 폴더에
│       ├── retrieval/      <- 검색 지표: v1 베이스라인(run_retrieval), D3·R1·서비스 경로 측정, 층별 재측정(11-03)
│       ├── embedding/      <- 임베딩 프록시(benchmark_embeddings)와 격자 본평가(11-02, 사전 등록 #16)
│       ├── search_compare/ <- 검색·청킹 방식 비교(hybrid_search, chunking_*)
│       ├── drafts/         <- 초안 검수 스냅샷(draft50_second_pass, draft52_validation)
│       ├── skill/          <- Skill·도구 개발 검증 요약
│       └── supervisor/     <- 수퍼바이저 모델 비교의 계획·문항별 결과·집계·provider 근거
│           ├── 2026-11-04-preflight-v5/  <- 초기 provider 호출 증거(manifest·DeepSeek row·smoke)
│           ├── 2026-11-04-routing-fix-smoke-v1/  <- Haiku·Luna 수정 후 smoke 증거
│           ├── 2026-11-04-stage1-v1/  <- 후보 5종 70문항 1회 비교
│               ├── manifest.json  <- 동결 입력·prompt·code hash와 작업 계획
│               ├── rows_anthropic__claude-haiku-5.5.json  <- Haiku 문항별 판정·오류·usage·latency
│               ├── rows_openai__gpt-6-luna.json  <- Luna 문항별 판정·오류·usage·latency
│               ├── rows_deepseek__deepseek-v4.1-flash.json  <- DeepSeek 중단 전 문항별 기록
│               ├── rows_meta__muse-glimmer-30b.json  <- Muse 문항별 판정·오류·usage·latency
│               ├── rows_cohere__command-a-plus.json  <- Cohere 문항별 판정·오류·usage·latency
│               ├── stage1_summary.json  <- 후보별 품질·오류·비용·latency 집계
│               └── provider_evidence.json  <- 후보별 provider·actual model·원본 artifact hash
│           ├── 2026-11-04-jev-stage1-ready-v1/  <- Jev 1차 70문항 원시 행·집계
│           ├── 2026-11-05-stage2-five-v1/  <- 기존 5종 2차 manifest·smoke·원시 행
│           ├── 2026-11-05-jev-stage2-v1/  <- Jev 2차 manifest·smoke·원시 행·집계
│           ├── 2026-11-05-stage2-comparison-v1/  <- 6종 2차 원시 행 재집계 정본
│           ├── 2026-11-05-stage3-five-v1/  <- 5종 3차 실행과 6종 공통 실행 metadata
│           │   ├── manifest.json  <- 동결 입력·prompt·code hash, 1~3차 계획 중 3차 350건
│           │   ├── preflight.json  <- 6종 공개 catalog·ZDR·가격·첫 job 예약액
│           │   ├── environment.json  <- Python·패키지·의존성 파일 hash
│           │   ├── execution.json  <- 6종 smoke·본 실행 인자·시각·종료·원시 hash
│           │   ├── rows_anthropic__claude-haiku-5.5.json  <- 3차 Haiku 문항별 결과
│           │   ├── rows_openai__gpt-6-luna.json  <- 3차 Luna 문항별 결과
│           │   ├── rows_deepseek__deepseek-v4.1-flash.json  <- 3차 DeepSeek 문항별 결과
│           │   ├── rows_meta__muse-glimmer-30b.json  <- 3차 Muse 문항별 결과
│           │   ├── rows_cohere__command-a-plus.json  <- 3차 Cohere 문항별 결과
│           │   ├── smoke_anthropic__claude-haiku-5.5.json  <- 3차 Haiku 호출 확인
│           │   ├── smoke_openai__gpt-6-luna.json  <- 3차 Luna 호출 확인
│           │   ├── smoke_deepseek__deepseek-v4.1-flash.json  <- 3차 DeepSeek 호출 확인
│           │   ├── smoke_meta__muse-glimmer-30b.json  <- 3차 Muse 호출·형식 오류 확인
│           │   └── smoke_cohere__command-a-plus.json  <- 3차 Cohere 호출 확인
│           ├── 2026-11-05-jev-stage3-v1/  <- Jev 3차 실행 결과
│           │   ├── manifest.json  <- 동결 입력·typed question 계약, 3차 70건
│           │   ├── smoke.json  <- 3차 Jev 호출·provider·usage 확인
│           │   ├── rows.json  <- 3차 Jev 문항별 결과·오류·usage
│           │   └── summary.json  <- Jev 실행기의 3차 집계
│           ├── 2026-11-05-stage3-comparison-v1/  <- API 없는 6종 1~3차 비교 정본
│           │   └── stage3_summary.json  <- 3차 지표·라우팅·3회 coverage·원시 hash
│           └── 2026-11-06-prompt-v0-v1/  <- Supervisor Prompt V0 세 후보 exact-provider smoke·13건 결과·통합 집계
│               ├── execution.json  <- 사용자 승인 상한·actual model/provider·호출·비용·출처 hash
│               ├── summary.json  <- 같은 dataset·의미 계약의 세 후보 공통 지표 정본
│               ├── langfuse_import.json  <- 기존 결과를 가져온 Dataset·Experiment 식별자와 외부 재조회 검증
│               ├── chat/  <- Luna·Haiku manifest·smoke·문항별 결과
│               └── jev/  <- Jev manifest·smoke·문항별 결과
│
├── tests/                  <- PR마다 CI가 돌리는 회귀 테스트. 영역별 하위 폴더, pytest가 하위 폴더까지 찾음 (고정: 루트 tests/)
│   ├── TESTS.md            <- 폴더 설명과 실행 명령
│   ├── api/                <- API와 로그인
│   │   ├── API.md          <- 폴더 설명
│   │   ├── test_health.py  <- /health 응답
│   │   ├── test_question.py <- 질문 API 인증 경계와 로그인 화면 확인
│   │   └── test_auth.py    <- 로그인·세션·잠금·관리자 API(DB 시험은 TEST_AUTH_DATABASE_URL이 있을 때만)
│   ├── graph/              <- 그래프 노드·조립
│   │   ├── GRAPH.md        <- 폴더 설명
│   │   ├── test_graph_supervisor.py  <- Supervisor V0 공통 계약과 상태 라우팅 검증
│   │   ├── test_graph_state.py  <- 상태 칸의 덮어쓰기·쌓기
│   │   ├── test_graph_read_input.py  <- 입력 나누기, 넷리스트 읽기, 저장소 밖 경로 차단
│   │   ├── test_graph_route.py  <- 라우팅 노드
│   │   ├── test_graph_search.py  <- 검색 노드의 품번 고르기
│   │   ├── test_graph_grade.py  <- 채점 노드의 품번·개정판 거르기
│   │   ├── test_graph_rewrite.py  <- 재작성 노드와 채점 뒤 갈림길
│   │   ├── test_graph_generate.py  <- 생성 노드의 근거 제한과 인용 검사
│   │   ├── test_graph_refuse.py  <- 거절 노드의 이유와 단서 요청
│   │   ├── test_graph_build.py  <- 그래프 조립 순서, 같은 대화 다음 턴 초기화
│   │   ├── test_graph_mcp_retriever.py  <- MCP 응답·세션·장애와 재검색 경로
│   │   └── test_graph_mcp_stdio.py  <- 격리 DB에서 실제 stdio MCP 검색 경로
│   ├── rag/                <- 검색과 오프라인 데이터 도구
│   │   ├── RAG.md          <- 폴더 설명
│   │   ├── test_rag_collect.py  <- 수집 도구(네트워크 없이)
│   │   ├── test_rag_parse.py  <- 파싱 도구의 Docling 없는 부분
│   │   ├── test_rag_chunk.py  <- 표 청크 규칙, 문서 키, manifest 크기
│   │   ├── test_rag_ingest.py  <- 적재 도구, 벡터 캐시
│   │   ├── test_voyage_rollout.py  <- voyage 적용 스크립트의 STOP 규칙·db/008 분기 글(가짜 연결, DB 없이)
│   │   ├── test_rag_retrieve.py  <- 검색 규칙(DB 시험은 TEST_DATABASE_URL이 있을 때만)
│   │   ├── test_rag_storage.py  <- halfvec 전환·재적재·정확 검색 계약
│   │   └── test_rag_subset.py  <- 문서 일부 뽑기 계약
│   ├── services/           <- 외부 호출 입구
│   │   ├── SERVICES.md     <- 폴더 설명
│   │   ├── test_llm.py     <- LLM 호출 입구: 데모 모드, 재시도 상한, 평가 예산
│   │   └── test_langfuse_prompts.py  <- Langfuse 프롬프트 컴파일·버전·전달 경계
│   ├── evals/              <- 평가셋 동결과 평가 실행기
│   │   ├── EVALS.md        <- 폴더 설명
│   │   ├── test_frozen_evals.py  <- 동결 해시 보호, v2 앞 50건 = v1, 평가 문항 id 선택
│   │   ├── test_retrieval_service.py  <- 서비스 경로 재측정 실행기의 지표·상위 5개 대조·백분위·오류 건너뛰기(가짜 retrieve)
│   │   ├── test_retrieval_d3.py  <- D3 검색 측정의 gold 쪽 풀기·페이지 단위 지표·실패 유형·부호 검정·임계값(데이터 없이)
│   │   ├── test_run_graph.py  <- 그래프 평가 실행의 실행 점수 추출
│   │   ├── test_score_answer.py  <- 답변·거절 5지표 채점기
│   │   ├── test_supervisor_models.py  <- 수퍼바이저 평가 실행·중단·집계·provider 증거 검증
│   │   ├── test_supervisor_jev.py  <- Jev typed answer·안전 gate·manifest 검증
│   │   ├── test_supervisor_stage3_report.py  <- 3차 집계 분모·라우팅·3회 비교 검증
│   │   ├── test_supervisor_prompt_v0_common.py  <- V0 표본 무결성·입력 격리·공통 분모 검증
│   │   ├── test_supervisor_prompt_v0.py  <- Luna·Haiku V0 입력·재시도·오프라인 plan·live gate 검증
│   │   ├── test_supervisor_prompt_v0_jev.py  <- Jev V0 공통 계약·입력 경계·typed answer·live gate 검증
│   │   ├── test_compare_supervisor_prompt_v0.py  <- V0 세 후보 hash·case·API별 지표 통합 집계 검증
│   │   ├── test_import_supervisor_prompt_v0_langfuse.py  <- V0 Langfuse 가져오기 payload·점수·중복 방지 검증
│   │   ├── test_skill_pair.py  <- Skill 비교 실행기의 경로·격리·예산
│   │   ├── test_embedding_grid.py  <- 격자 평가 실행기의 순위·요약·카드 묶기와 격자 결과 파일 78칸 재계산 일치
│   │   ├── test_retrieval_layers.py  <- 층별 재측정의 판정 규칙·토큰화와 층 결과 파일 요약 재계산 일치
│   │   └── test_bit_search.py  <- 비트 검색의 recall 계산과 결과 파일에서 다시 계산한 값이 문서와 일치
│   ├── mcp_skill/          <- MCP 서버 도구 5종(오프라인, 외부 호출 0회)
│   │   ├── MCP_SKILL.md    <- 폴더 설명
│   │   └── test_mcp_server.py  <- 코퍼스 검색·문서 조회·웹 후보·PDF 무결성·회로 조회의 수용 기준(SPEC 8.7)
│   ├── judge/              <- 판정 코드 시험. 판정 코드와 같은 PR에서 넣음
│   │   └── JUDGE.md        <- 폴더 설명
│   ├── repo/               <- 저장소 구조 규칙
│   │   ├── REPO.md         <- 폴더 설명
│   │   └── test_repo_layout.py  <- 이 문서의 트리·이름 규칙·폴더 설명 파일·한 폴더 한 종류를 지킴
│   └── fixtures/           <- 단위 테스트용 가공 회로(지금은 .gitkeep)
│
├── scripts/                <- 서비스 코드 밖에서 손으로 돌리는 일회성 측정·점검 스크립트, 주제별 하위 폴더
│   ├── SCRIPTS.md          <- 폴더 설명과 실행 방법
│   ├── auth/               <- 로그인 측정
│   │   ├── AUTH.md         <- 폴더 설명
│   │   ├── auth_boundary_after_merge.py  <- 로그인 잠금·세션 만료 경계 시각 실측
│   │   └── measure_scrypt_concurrent.py  <- 동시 scrypt 상한과 프로세스 메모리 실측(Windows 전용)
│   ├── langfuse/           <- Langfuse 점검
│   │   ├── LANGFUSE.md     <- 폴더 설명
│   │   └── langfuse_skill_check.py  <- Langfuse 프롬프트·Skill 연결을 합성 요청으로 점검
│   ├── bit_search/         <- 비트 후보 + 정확 재정렬 검색 속도·recall 실측
│   │   ├── BIT_SEARCH.md   <- 폴더 설명
│   │   └── bit_search_exp.py  <- 실험 표 exp_bq를 만들어 시간·recall@50을 재고 지움(측정 당시 DB용)
│   ├── hf_jobs/            <- Hugging Face Jobs로 GPU 임베딩을 돌리는 스크립트
│   │   ├── HF_JOBS.md      <- 폴더 설명
│   │   ├── hf_job.py       <- HF Jobs에서 GPU 모델로 카드·질의를 임베딩해 비공개 데이터셋에 올림
│   │   └── hf_data.py      <- 카드·질의를 비공개 저장소로 올리고 결과 벡터를 받아 검증·삭제
│   ├── db/                 <- 운영 DB 손 작업
│   │   ├── DB.md           <- 폴더 설명
│   │   └── voyage_rollout.py  <- voyage-4-large 적용 점검·마이그레이션(db/008)·적재 검증(DB 변경은 migrate만)
│   └── results/            <- 측정 원시 결과(평가 지표가 아님). <무엇>_<날짜>.json을 주제 폴더에
│       ├── auth/           <- 로그인 경계·동시 scrypt
│       ├── storage/        <- DB 저장 형식·용량
│       ├── parser/         <- 파서 정확도·속도, GPU 파싱 로그·재현율
│       ├── hnsw/           <- HNSW 대 정확 검색
│       └── bit_search/     <- 비트 후보 + 정확 재정렬 검색 속도·recall(11-03)
│
├── docs/                   <- 사람이 읽는 문서: 과제 문서, 결정, 작업서, 조사, 제출물, 작업 기록
│   ├── DOCS.md             <- 폴더 설명
│   ├── TOPIC.md            <- 통과한 주제서 (고정: 과제 가이드 경로)
│   ├── GATES.md            <- 필수 게이트 G1~G7 자기 점검과 증거 (고정: 과제 가이드 경로)
│   ├── evaluation-prep.md  <- 배점·가산 항목별 준비 점검
│   ├── 조원-계약서.md      <- 요청 흐름, 담당별 수정 경로, 모듈 사이 함수 계약
│   ├── glossary.md         <- 용어집: 문서에서 쓰는 말과 예전에 쓴 말
│   ├── adr/                <- 조 결정 기록. 결정 하나에 파일 하나(0001-한국어-제목.md부터)
│   │   └── ADR.md          <- 폴더 설명과 결정 목록
│   ├── specs/              <- 기능 작업서: SPEC.md에 없는 기능을 에이전트에게 시키기 전에 씀
│   │   ├── SPECS.md        <- 폴더 설명
│   │   ├── _example.md     <- 강사 작업서 형식 예시 (고정: AGENTS.md가 가리킴)
│   │   ├── login-auth.md   <- 로그인과 사용자 식별
│   │   ├── login-completion-plan.md  <- 암호 처리·개인정보·인증 DB 적재의 마무리 작업 목록
│   │   ├── rag-pipeline.md <- 데이터시트 수집부터 하이브리드 검색까지
│   │   ├── mcp-tool-prompt.md  <- MCP 도구 선택·결과 해석 프롬프트
│   │   ├── mcp-search-tools.md  <- MCP 도구 API·입출력·수용 기준
│   │   ├── mcp-graph-integration.md  <- search_corpus와 LangGraph 검색 주입 계약
│   │   ├── mcp-graph-integration-plan.md  <- MCP 그래프 통합의 테스트 우선 구현 계획
│   │   └── supervisor-v0-langfuse-import.md  <- 완료된 V0 결과의 Langfuse Dataset·Experiment 가져오기 계약
│   ├── superpowers/        <- 사용자와 합의한 설계와 단계별 구현 계획
│   │   ├── SUPERPOWERS.md  <- 폴더 설명
│   │   ├── specs/
│   │   │   └── 2026-11-05-supervisor-prompt-v0-design.md  <- Supervisor Prompt V0 설계
│   │   └── plans/
│   │       └── 2026-11-05-supervisor-prompt-v0.md  <- Supervisor Prompt V0 구현 계획
│   ├── experiments/        <- 실험·평가 작업서: 무엇을 어떤 조건으로 잴지 정한 계약
│   │   ├── EXPERIMENTS.md  <- 폴더 설명
│   │   ├── embedding-model-baseline.md  <- 임베딩 모델 예비 기준선
│   │   ├── embedding-candidate-runner.md  <- 임베딩 후보 확장 평가기 설계
│   │   ├── embedding-voyage-candidates.md  <- Voyage 임베딩 후보 추가
│   │   ├── corpus-storage-budget.md  <- 원본 코퍼스 유지와 halfvec 저장 검증
│   │   ├── evaluation-draft-30.md  <- 난이도별 평가 문항 30건 초안 작성
│   │   ├── evaluation-draft-52.md  <- 정보 부족 기준과 50건 초안 작성(파일명의 52는 당시 이력)
│   │   ├── answer-refusal-scorer.md  <- 답변·거절 5지표 규칙 기반 채점기 설계와 수용 기준
│   │   ├── supervisor-model-comparison.md  <- 수퍼바이저 후보 5종 70문항 1회 비교와 Luna 최종 선정 근거
│   │   ├── supervisor-model-comparison-postregistration.md  <- 수퍼바이저 5종 비교의 실제 조건·변경·한계 사후등록
│   │   ├── supervisor-stage2-six-models.md  <- 6종 2차 공동 평가 계약
│   │   └── supervisor-stage3-six-models.md  <- 6종 3차 실행 전 평가 계약
│   ├── research/           <- 조사·실측 기록과 합의 전 제안. 결정이 아님
│   │   ├── RESEARCH.md     <- 폴더 설명
│   │   ├── embedding-candidate-investigation.md  <- 임베딩 후보 13종 조사·실행·중단 사유
│   │   ├── model-licenses.md  <- 임베딩 후보 라이선스와 공개 범위
│   │   ├── skill-feasibility.md  <- 도메인 Skill 후보 조사
│   │   ├── auth-login-verification.md  <- 로그인·세션·scrypt 실측 기록
│   │   ├── auth-feedback-key-verification.md  <- 로그인 피드백·AUTH_SECRET 검증 실측
│   │   ├── email-encryption-options.md  <- 로그인 이메일 암호화 정책 선택지(팀 결정 전)
│   │   ├── supabase-auth-test-runbook.md  <- 격리 Supabase 인증 테스트 프로젝트·보안 점검·재개 절차
│   │   ├── ci-proposal.md  <- CI 사용량 절감 제안(합의 전)
│   │   ├── mcp-collaboration-handoff.md  <- MCP·LangGraph 공동작업 인수인계 스냅샷
│   │   ├── jev-supervisor-evaluation-handoff.md  <- Jev 1차 실측·2차 인수인계
│   │   ├── supervisor-stage2-results.md  <- 수퍼바이저 6종 2차 실측·비교·집계 한계
│   │   ├── supervisor-stage2-brief-report.md  <- 2차 핵심 수치·1차 대비 간단 보고서
│   │   ├── supervisor-stage3-results.md  <- 6종 3차 전체 수치·1~3차 안정성·PR 근거
│   │   ├── supervisor-stage3-brief-report.md  <- 6종 3차 핵심 수치·2차 대비 변화
│   │   ├── mcp-docling-verification-2026-11-03.md  <- 저장소 PDF 표본 대조 기록
│   │   ├── mcp-offline-verification-2026-11-03.md  <- DB 없는 MCP·PDF 표본 점검 기록
│   │   ├── mcp-tool-candidates-draft.md  <- MCP·웹 검색 도구 후보 조사·실측
│   │   ├── mcp-tool-contract-review.md  <- MCP 도구 입출력·호출처 검토
│   │   ├── mcp-tool-implementation-plan.md  <- MCP 구현 범위·우선순위 제안
│   │   ├── mcp-two-person-work-plan.md  <- MCP·LangGraph 역할 분담 제안
│   │   ├── tsc-public-part-verification-options.md  <- 공개 품번 확인 정책 선택지
│   │   ├── web-search-filter-comparison.md  <- 웹 검색 필터 비교 실측
│   │   ├── web-search-results-interpretation.md  <- 웹 검색 결과 해석과 한계
│   │   ├── retrieval-baseline-analysis.md  <- 동결 v1 검색 베이스라인 3방식 문항별 대조·실패 유형 분석
│   │   ├── embedding-grid-eval-2026-11-02.md  <- 임베딩 6종 × 검색 방식 격자 본평가 78칸 전체 표·시간·사전 등록 대조
│   │   ├── retrieval-layered-rerun-2026-11-03.md  <- 검색 조합 층별 재측정(질의·토큰화·임베딩·리랭커) 사전 등록과 결과
│   │   ├── bit-search-measurement-2026-11-03.md  <- 비트 후보 + pgvector 재정렬 속도·recall 실측
│   │   └── market-user-journey.md  <- 문제·시장 근거: 사실·가설 구분, 페르소나, 고객 여정 맵, 대체재 5문항 비교 설계
│   ├── deliverables/       <- 최종 제출 문서 양식 (고정: 과제 가이드 G7)
│   │   ├── DELIVERABLES.md <- 폴더 설명
│   │   ├── ai_tools_log.md <- AI 코딩 도구 사용 기록
│   │   ├── failure_analysis.md  <- 실패 사례 분석 글
│   │   ├── portfolio.md    <- 포트폴리오 1장 양식
│   │   ├── portfolio-<이름>.md  <- 조원별 포트폴리오, portfolio.md를 복사해 작성 (예정)
│   │   └── langfuse/       <- Langfuse 대시보드 스크린샷 3장 이상(트레이스 상세 1장 포함, 지금은 .gitkeep)
│   └── worklog/            <- 조원별 작업 기록. 한 사람에 파일 하나, 소문자 이름
│       ├── WORKLOG.md      <- 폴더 설명과 기록 형식
│       ├── jeongun.md      <- 하정운(조장·오케스트레이터)
│       ├── jaehun.md       <- 김재훈
│       ├── osc.md          <- 오세창
│       └── sth.md          <- 심태현
│
└── extras/                 <- 가산 중 이미지에 들어가지 않는 작업. Dockerfile이 복사하지 않음
    ├── EXTRAS.md           <- 폴더 설명
    └── finetune/           <- 가산: 파인튜닝 학습 코드와 비교 결과. 아직 설명 파일만 있음
        └── FINETUNE.md     <- 폴더 설명
```

저장소 밖 같은 상위 폴더(`../`)에는 코퍼스 전체(`../corpus/`), 실험 자료(`../전자_데이터시트/`), 회의록이 있습니다. 저장소 파일이 아니므로 위 트리에 넣지 않습니다.

## 폴더 설명 파일과 담당

| 폴더 | 설명 파일 | 담당 |
|---|---|---|
| `backend/` | [BACKEND.md](backend/BACKEND.md) | 서비스·운영 |
| `backend/graph/` | [GRAPH.md](backend/graph/GRAPH.md) | 에이전트 |
| `backend/prompts/` | [PROMPTS.md](backend/prompts/PROMPTS.md) | 에이전트 |
| `backend/rag/` | [RAG.md](backend/rag/RAG.md) | 검색·데이터 |
| `backend/services/` | [SERVICES.md](backend/services/SERVICES.md) | 서비스·운영 |
| `backend/judge/` | [JUDGE.md](backend/judge/JUDGE.md) | 에이전트 |
| `backend/web/` | [WEB.md](backend/web/WEB.md) | 서비스·운영 |
| `backend/mcp_skill/` | [MCP_SKILL.md](backend/mcp_skill/MCP_SKILL.md) | 가산을 시작할 때 정함 |
| `data/` | [DATA.md](data/DATA.md) | 검색·데이터 |
| `data/corpus/` | [CORPUS.md](data/corpus/CORPUS.md) | 검색·데이터 |
| `data/circuits/` | [CIRCUITS.md](data/circuits/CIRCUITS.md) | 평가·문서 |
| `data/demo/` | [DEMO.md](data/demo/DEMO.md) | 서비스·운영 |
| `db/` | [DB.md](db/DB.md) | 서비스·운영 |
| `db/manual/` | [MANUAL.md](db/manual/MANUAL.md) | 서비스·운영 |
| `db/schema/` | [SCHEMA.md](db/schema/SCHEMA.md) | 서비스·운영 |
| `evals/` | [EVALS.md](evals/EVALS.md) | 평가·문서 |
| `evals/drafts/` | [DRAFTS.md](evals/drafts/DRAFTS.md) | 평가·문서 |
| `evals/inputs/` | [INPUTS.md](evals/inputs/INPUTS.md) | 평가·데이터 |
| `evals/docker/` | [DOCKER.md](evals/docker/DOCKER.md) | 평가·문서 |
| `evals/guides/` | [GUIDES.md](evals/guides/GUIDES.md) | 평가·문서 |
| `evals/runners/` | [RUNNERS.md](evals/runners/RUNNERS.md) | 평가·문서 |
| `evals/samples/` | [SAMPLES.md](evals/samples/SAMPLES.md) | 검색·데이터 |
| `tests/` | [TESTS.md](tests/TESTS.md) | 각 모듈 담당 |
| `tests/api/` | [API.md](tests/api/API.md) | 서비스·운영 |
| `tests/graph/` | [GRAPH.md](tests/graph/GRAPH.md) | 에이전트 |
| `tests/rag/` | [RAG.md](tests/rag/RAG.md) | 검색·데이터 |
| `tests/services/` | [SERVICES.md](tests/services/SERVICES.md) | 서비스·운영 |
| `tests/evals/` | [EVALS.md](tests/evals/EVALS.md) | 평가·문서 |
| `tests/mcp_skill/` | [MCP_SKILL.md](tests/mcp_skill/MCP_SKILL.md) | 가산을 시작할 때 정함 |
| `tests/judge/` | [JUDGE.md](tests/judge/JUDGE.md) | 에이전트 |
| `tests/repo/` | [REPO.md](tests/repo/REPO.md) | 조장 |
| `scripts/` | [SCRIPTS.md](scripts/SCRIPTS.md) | 각 모듈 담당 |
| `scripts/auth/` | [AUTH.md](scripts/auth/AUTH.md) | 서비스·운영 |
| `scripts/db/` | [DB.md](scripts/db/DB.md) | 서비스·운영 |
| `scripts/bit_search/` | [BIT_SEARCH.md](scripts/bit_search/BIT_SEARCH.md) | 서비스·운영 |
| `scripts/hf_jobs/` | [HF_JOBS.md](scripts/hf_jobs/HF_JOBS.md) | 검색·데이터 |
| `scripts/langfuse/` | [LANGFUSE.md](scripts/langfuse/LANGFUSE.md) | 에이전트 |
| `docs/` | [DOCS.md](docs/DOCS.md) | 평가·문서 |
| `docs/adr/` | [ADR.md](docs/adr/ADR.md) | 결정을 낸 담당 |
| `docs/specs/` | [SPECS.md](docs/specs/SPECS.md) | 그 기능의 담당 |
| `docs/superpowers/` | [SUPERPOWERS.md](docs/superpowers/SUPERPOWERS.md) | 그 기능의 담당 |
| `docs/experiments/` | [EXPERIMENTS.md](docs/experiments/EXPERIMENTS.md) | 그 실험의 담당 |
| `docs/research/` | [RESEARCH.md](docs/research/RESEARCH.md) | 쓴 사람 |
| `docs/deliverables/` | [DELIVERABLES.md](docs/deliverables/DELIVERABLES.md) | 평가·문서 |
| `docs/worklog/` | [WORKLOG.md](docs/worklog/WORKLOG.md) | 각자 자기 파일 |
| `extras/` | [EXTRAS.md](extras/EXTRAS.md) | 가산을 시작할 때 정함 |
| `extras/finetune/` | [FINETUNE.md](extras/finetune/FINETUNE.md) | 가산을 시작할 때 정함 |

담당은 가이드의 역할 4개(검색·데이터, 에이전트, 서비스·운영, 평가·문서)입니다. 사람 배정은 [README.md](README.md) 조원 표에 있습니다.

## 이름 규칙

[ADR 0012](docs/adr/0012-폴더-설명-파일은-대문자-폴더명으로-되돌린다.md)를 따릅니다. `tests/repo/test_repo_layout.py`가 PR마다 검사합니다.

- **폴더 설명 파일**은 폴더마다 `<대문자 폴더명>.md` 하나입니다(`backend/BACKEND.md`, `backend/mcp_skill/MCP_SKILL.md`). 역할, 넣는 것, 넣지 않는 것, 담당, 파일을 적습니다. `README.md`는 루트 대표 문서 하나뿐입니다.
- **대문자 마크다운**은 루트 대표 문서 6개(`README.md`, `SOJAFIT.md`, `SPEC.md`, `AGENTS.md`, `CLAUDE.md`, `EVAL_REPORT.md`)와 폴더 설명 파일만 씁니다. 그 밖의 문서는 소문자입니다. 예외는 다른 곳이 이름을 정한 네 개입니다: `docs/TOPIC.md`·`docs/GATES.md`(과제 가이드), `backend/mcp_skill/skills/SKILL.md`(Skill 관례, 코드가 읽음), `.github/PULL_REQUEST_TEMPLATE.md`(GitHub 관례). 데이터 파일(`FROZEN.json`, 데이터시트 PDF, 회로 원본)은 받은 이름이나 코드가 읽는 이름을 그대로 씁니다.
- **대문자의 효과와 한계**
  - GitHub 파일 목록, 터미널 `ls`, `git ls-files`는 대문자 이름을 소문자보다 먼저 정렬해 폴더 설명 파일이 파일 목록 맨 위에 옵니다(2026-11-03 확인). 같은 폴더에 다른 대문자 문서가 없어야 이 효과가 살아 있어서, 대문자를 아래 예외 밖에서 쓰지 않습니다.
  - VS Code 탐색기와 macOS Finder는 기본 설정에서 대소문자를 섞어 정렬해 이 효과가 없습니다. GitHub은 `README.md`만 폴더 아래에 펼쳐 보여 주고 `<대문자 폴더명>.md`는 눌러야 열립니다. 그래서 설명 파일은 이 문서의 트리와 표에서 링크로 찾습니다.
  - macOS 기본 파일시스템은 대소문자를 구분하지 않고, 이 저장소의 git 설정도 `core.ignorecase=true`입니다. 대소문자만 바꾸는 이름 변경은 `git mv a.md tmp.md && git mv tmp.md A.md` 두 단계로 해야 git에 남습니다. 대소문자만 다른 두 파일(`readme.md`·`README.md`)은 한 폴더에 둘 수 없습니다.
- 폴더 설명은 두 단계 폴더까지만 둡니다. 더 깊은 폴더(`backend/mcp_skill/skills/` 등)는 위 폴더 설명 파일에 적습니다. 원시 결과·시험 데이터만 담는 폴더(`evals/results/`, `scripts/results/`, `tests/fixtures/`), `.github/`, `data/circuits/collected/`에는 설명 파일을 두지 않습니다.
- **한 폴더 바로 아래에는 한 종류 파일만** 둡니다(코드·데이터·문서·SQL·설정 중 하나, 설명 파일과 `.gitkeep`은 빼고 셈). 종류가 섞이면 성격별 하위 폴더로 나눕니다(예: `evals/runners/`, `evals/guides/`). 저장소 루트는 도구가 루트에서 찾는 파일이라 예외입니다.
- 아직 없는 파일은 트리에 `(예정)`을 붙여 적고, 비어 있는 폴더는 `.gitkeep`으로 자리를 둡니다. 실제로 만들면 같은 PR에서 `(예정)`을 지웁니다.
- 결정 기록은 `docs/adr/NNNN-한국어-제목.md`, 기능 작업서는 `docs/specs/<english-kebab>.md`, 실험 작업서는 `docs/experiments/<english-kebab>.md`, 조사 기록은 `docs/research/<english-kebab>.md`입니다. 원시 결과 파일은 `<무엇>_<YYYY-MM-DD>.json`입니다.
- 강사 스캐폴드와 과제 가이드의 고정 경로(트리의 `(고정)`)는 옮기지 않습니다.

## 파일을 만들거나 옮길 때

1. 위 트리에서 `<-` 설명이 맞는 폴더를 고릅니다. 맞는 폴더가 없으면 가장 가까운 폴더에 억지로 넣지 않고, 새 폴더를 이 트리·표·설명 파일과 함께 만드는 PR을 따로 냅니다.
2. 같은 PR에서 이 트리에 그 파일 한 줄(`<-` 설명 포함)과 그 폴더 설명 파일의 "파일" 목록 한 줄을 고칩니다. 원시 결과 폴더는 트리의 묶음 설명만 맞으면 됩니다.
3. 넣으려는 폴더에 다른 종류 파일이 이미 있으면 그 폴더에 섞지 않고 성격별 하위 폴더를 만들거나 기존 하위 폴더에 넣습니다. 트리에 `(예정)`으로 적힌 자리가 있으면 그 이름을 쓰고 `(예정)`을 지웁니다.
4. 폴더 설명 파일의 "넣는 것"을 새 파일에 맞춰 넓히지 않습니다. 넓혀야 한다면 폴더 역할이 바뀌는 것이므로 이 트리의 `<-` 설명부터 고칩니다.

## 처음 할 일

1. 키 없이 `docker compose up`(`.env`가 없으면 데모 모드)으로 `/health`가 뜨는지 확인합니다. 실제 모드는 `cp .env.example .env`(`DEMO_MODE=0`) 뒤 키와 `AUTH_SECRET`을 채웁니다.
2. 위 트리에서 손댈 폴더를 고르고 그 폴더의 `<대문자 폴더명>.md`부터 읽습니다.
