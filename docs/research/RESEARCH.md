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
- `ci-proposal.md` — CI 사용량 절감 제안(합의 전, workflow 미변경)
- `mcp-tool-candidates-draft.md` — MCP·웹 검색 후보와 비용 비교 초안
- `web-search-results-interpretation.md` — 비동결 30문항 웹 검색 결과 해석
- `web-search-filter-comparison.md` — 세 검색 도구의 TSC 도메인 필터 전후 비교와 PDF 표본 확인
- `mcp-tool-implementation-plan.md` — MCP 도구 구현 현황과 후속 선행 조건 기록
- `mcp-offline-verification-2026-11-03.md` — 저장소 표본의 DB 없는 MCP·회로·PDF 점검 결과
- `mcp-docling-verification-2026-11-03.md` — TSC PDF 3건의 Docling·pdfplumber 대조 결과
- `tsc-public-part-verification-options.md` — 코퍼스 밖 TSC 품번의 공개 확인·외부 전송 방안 초안
