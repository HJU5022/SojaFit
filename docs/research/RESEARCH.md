# research

## 역할
- 이 폴더: 조사·실측 기록과 합의 전 제안을 둡니다. 결정이 아닙니다.
- 넣는 것: `<english-kebab>.md`. 조사일·기준 커밋·측정 환경과 한계를 밝힌 기록, 아직 합의하지 않은 제안.
- 넣지 않는 것: 결정(`../adr/`), 무엇을 어떤 조건으로 잴지 정한 작업서(`../experiments/`), 기능 작업서(`../specs/`), 측정 원시 JSON(`../../scripts/results/`, `../../evals/results/`), 조원별 작업 기록(`../worklog/`).
- 담당: 쓴 사람

## 파일
- `embedding-candidate-investigation.md` — 임베딩 후보 13종을 넣은 이유, 개별 조사·실행 과정, 중단 사유와 다음 평가 조건
- `model-licenses.md` — 임베딩 후보별 고정 revision, 라이선스·약관, 운영/연구 분류와 GitHub 포함 여부
- `skill-feasibility.md` — 도메인 Skill 후보와 기존 기능과의 경계, 선행 조건, 작업 순서 조사
- `auth-login-verification.md` — 로그인·세션·scrypt 로컬 실측 기록. 스크립트는 `scripts/`, 원시 JSON은 `scripts/results/`(`auth_boundary_*`, `scrypt_concurrent_*`)
- `auth-feedback-key-verification.md` — 로그인 피드백·`AUTH_SECRET` 실제 키 사용과 역할별 실측 기록
- `email-encryption-options.md` — 로그인 이메일 필드 암호화와 최소 수집 정책의 팀 논의 선택지
- `supabase-auth-test-runbook.md` — Supabase 인증 테스트 프로젝트 생성, 스키마 점검, RLS 차단 사유와 재개 절차
- `ci-proposal.md` — CI 사용량 절감 제안(합의 전, workflow 미변경)
- `mcp-collaboration-handoff.md` — MCP 서버·LangGraph 공동작업 인수인계 스냅샷과 미결 항목
- `mcp-docling-verification-2026-11-03.md` — 저장소 PDF 3건의 Docling·pdfplumber 표본 대조와 한계
- `mcp-offline-verification-2026-11-03.md` — DB 없이 수행한 MCP·PDF·회로 표본 점검 기록
- `mcp-tool-candidates-draft.md` — MCP·웹 검색 도구 후보 조사와 비교 실측 해석
- `mcp-tool-contract-review.md` — 다섯 MCP 도구의 입출력·호출처 검토 및 연결 제안
- `mcp-tool-implementation-plan.md` — MCP 도구 범위·우선순위와 후속 통합 계획 초안
- `mcp-two-person-work-plan.md` — MCP·LangGraph 역할 분담 제안(팀 합의 전)
- `tsc-public-part-verification-options.md` — 코퍼스 밖 공개 품번 확인 정책 선택지
- `web-search-filter-comparison.md` — 웹 검색 TSC 필터 유무 비교 실측 기록
- `web-search-results-interpretation.md` — 웹 검색 비교 결과 지표 해석과 한계
- `retrieval-baseline-analysis.md` — 동결 v1(`dataset_v1.jsonl`) 검색 베이스라인 3방식(`dense`·`bm25`·`hybrid`) 19문항 대조, 회귀 문항 및 실패 유형 4가지 분석, 채점 산식·한계 기록
- `market-user-journey.md` — 문제·시장 근거(채용 공고 237건 중 LLM/RAG 77건 역량 매핑, 사용자·지불 주체 사실/가설 구분, 페르소나 2종, 6단계 고객 여정 맵, 범용 챗봇 5문항 비교, 현재 서비스 약점, 외부 검토 양식)
