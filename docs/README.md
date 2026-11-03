# docs

## 역할
- 이 폴더: 주제서, 조원 계약서, 게이트 증거, 조 결정 기록, 작업서, 제출물, 작업 기록, 평가 보충·조사·실측 기록을 둡니다.
- 넣는 것: 아래 파일과 하위 폴더.
- 넣지 않는 것: 기능의 정본(루트 `SPEC.md`), 평가 리포트(루트 `EVAL_REPORT.md`), 저장소 지도(루트 `SOJAFIT.md`).
- 담당: 평가·문서

## 파일
- [skill-feasibility.md](skill-feasibility.md) — 도메인 Skill 후보·기존 기능과의 경계·초안의 선행 조건·Langfuse 연결을 포함한 작업 순서 조사
- `TOPIC.md` — 강사에게 낸 주제서를 옮겨 두는 곳
- `조원-계약서.md` — 조원 간 계약서(각자 수정하는 경로, 모듈 사이 함수, 코드가 읽는 파일과 환경변수, 오프라인 규칙)와 강사가 준 요청 흐름·설계 질문
- `GATES.md` — 필수 게이트 G1~G7을 어디서 채우는지와 증거, 테스트를 일부러 깨뜨려 본 기록 표(3건 이상 채울 곳)
- `adr/` — 조 결정 기록. [README.md](adr/README.md)
- `specs/` — SPEC에 없는 기능이 생길 때 쓰는 작업서. [README.md](specs/README.md)
- `deliverables/` — 제출물. [README.md](deliverables/README.md)
- `worklog/` — 조원별 작업 기록. [README.md](worklog/README.md)
- [EVALUATION.md](EVALUATION.md) — 기존 문서에 없는 평가 축·시장 근거·가산 준비 항목
- [CI_PROPOSAL.md](CI_PROPOSAL.md) — 현재 workflow에 대한 절감 보완 제안(미적용)
- [mcp-tool-candidates-draft.md](mcp-tool-candidates-draft.md) — MCP·웹 검색 후보, 비용 비교와 팀 논의 초안
- [auth-login-verification.md](auth-login-verification.md) — 인증 세션·시간 경계·scrypt 로컬 실측 기록. 측정 스크립트는 `scripts/`, 원시 결과는 `evals/results/`
- [auth-feedback-key-verification.md](auth-feedback-key-verification.md) — 로그인 피드백·AUTH_SECRET 실제 키 사용과 역할별 실측
- [model-licenses.md](model-licenses.md) — 임베딩 후보별 고정 revision, 라이선스·약관, 운영/연구 분류와 GitHub 포함 여부
- [embedding-candidate-investigation.md](embedding-candidate-investigation.md) — 임베딩 후보 13종을 넣은 이유, 개별 조사·실행 과정, 중단 사유와 다음 평가 조건

- [web-search-results-interpretation.md](web-search-results-interpretation.md) — 30문항 웹 검색 결과표와 측정 항목별 해석.

- [web-search-filter-comparison.md](web-search-filter-comparison.md) — 세 도구의 TSC 필터 전후 30문항 비교와 3건 PDF 확인.

- [mcp-tool-implementation-plan.md](mcp-tool-implementation-plan.md) — MCP 도구 구현 상태, 초기 범위와 후속 선행 조건.

- [mcp-offline-verification-2026-11-03.md](mcp-offline-verification-2026-11-03.md) — 저장소 표본의 DB 없는 MCP·회로·PDF 점검 결과.

- [mcp-docling-verification-2026-11-03.md](mcp-docling-verification-2026-11-03.md) — TSC PDF 3건의 Docling·pdfplumber 숫자·대표 행 대조 결과.

- [tsc-public-part-verification-options.md](tsc-public-part-verification-options.md) — 코퍼스 밖 TSC 품번의 공개 확인 및 외부 전송 방안 팀 논의 초안.
