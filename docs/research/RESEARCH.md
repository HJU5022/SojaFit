# research

## 역할
- 이 폴더: 조사·검증·실측 보고를 둡니다(합의 전 제안 포함). 결정이 아닙니다.
- 넣는 것: `<english-kebab>.md`. 조사일·기준 커밋·측정 환경과 한계를 밝힌 기록, 아직 합의하지 않은 제안.
- 넣지 않는 것: 결정(`../adr/`), 무엇을 어떤 조건으로 잴지 정한 작업서(`../experiments/`), 기능 작업서(`../specs/`), 측정 원시 JSON(`../../scripts/results/`, `../../evals/results/`), 조원별 작업 기록(`../worklog/`).
- 담당: 쓴 사람

## 파일
- [frontend-schematic-work-summary-2026-11-15.md](frontend-schematic-work-summary-2026-11-15.md) — 프런트 오류·회로도 검색 개선 17개 작업의 문제·원인·해결·효과와 직접 검증/미검증 범위
- [schematic-search-verification-2026-11-15.md](schematic-search-verification-2026-11-15.md) — CDFER 11장·1N4148 후보 실검증과 한도 소진으로 중단한 1N4007의 결과·한계
- [resolved-issues-summary-2026-11-15.md](resolved-issues-summary-2026-11-15.md) — 회로도 검색·입력·판정·대화 기억의 해결·검증 완료 항목 공유 보고서
- [docker-cold-start-measurements.md](docker-cold-start-measurements.md) — 11월 13~14일 Docker G2, 첫 기능·첫 회로도와 운영 첫 요청의 측정값·방법 출처
- [db-redesign/](db-redesign/summary.md) — 서비스 DB 재설계(11-11) 설계 문서 7개(이력)(`summary.md` 요약, `as-is-*` 현재 구조, `to-be-*` 목표 구조·영향 지도). 검증 스크립트는 `scripts/db/verify_redesign/`
- [sojafit-domain-jobs-2026-11-12.md](sojafit-domain-jobs-2026-11-12.md) — 도메인 유사 분야 채용 공고 72건(2026-11-12 기준): 역할·후보 그룹, 공고 링크, 분야별 한계
- [d9-outside-evidence-2026-11-11.md](d9-outside-evidence-2026-11-11.md) — D9용 저장소 밖 증거 A~D 이관 목록(판정진단·v4h summary/manifest·#48+#49 원시)·아직 없는 216건 표주석 원시
- [injection-case-review-packet.md](injection-case-review-packet.md) — 본실측03 우선 31건과 별도 스모크08 우선 1건의 질문·최종응답 원문, 측정 청크/회로/공격면, 제조사 PDF 대조자료. 검토 기록의 원시는 `evals/results/threads/`의 해당 jsonl `human_review` 필드
- [injection-results.md](injection-results.md) — 인젝션 실측 결과(정본): 원시 `human_review` 필드·해시 표(1절), 스모크01~08·본실측01~03의 결과·예산·사례별 관찰, 저장 응답 검토, 신뢰 경계·C1/C2·P4 별도 측정(6절)
- [injection-preregistration-proposal.md](injection-preregistration-proposal.md) — 인젝션 실험의 SPEC 반영·사전등록 제안 8건 중 SPEC 반영 5건은 미반영, 사전등록 3건은 `preregister.md`에 반영(계획)
- [thread-memory-operations-review.md](thread-memory-operations-review.md) — Thread·승인 기억 운영 검증 결과(2026-11-09~12 스냅샷)와 정본 반영 제안
- [embedding-candidate-investigation.md](embedding-candidate-investigation.md) — 임베딩 후보 13종을 넣은 이유, 후보별 실행 범위, 중단·제외 사유(이력)
- [model-licenses.md](model-licenses.md) — 임베딩 후보별 고정 revision, 라이선스·약관, 운영/연구 분류와 GitHub 포함 여부
- [skill-feasibility.md](skill-feasibility.md) — 도메인 Skill 후보와 기존 기능과의 경계, 선행 조건, 작업 순서 조사
- [auth-login-verification.md](auth-login-verification.md) — 로그인·세션·scrypt·AUTH_SECRET 로컬 실측(이력): 잠금·세션 만료 경계, 세션 분리, scrypt 동시 실행 메모리. 스크립트는 `scripts/auth/`, 원시 JSON은 `scripts/results/auth/`
- [email-encryption-options.md](email-encryption-options.md) — 로그인 이메일 저장 보호 선택지 A~D, 현재 `users.login_id` 구조, 미결 질문(제안)
- [supabase-auth-test-runbook.md](supabase-auth-test-runbook.md) — Supabase 인증 테스트 프로젝트 점검 결과: 스키마 점검, RLS 차단 사유, 재개 절차
- [ci-proposal.md](ci-proposal.md) — CI 사용량 절감 제안과 현재 workflow 설정(제안)
- [supervisor-stage2-results.md](supervisor-stage2-results.md) — 수퍼바이저 6종 2차 원시 행 대조·비용·집계 한계
- [supervisor-stage3-results.md](supervisor-stage3-results.md) — 6종 3차 전체 실측·1~3차 비교·라우팅 모순·PR 검토용 근거
- [mcp-docling-verification-2026-11-03.md](mcp-docling-verification-2026-11-03.md) — 저장소 PDF 3건의 Docling·pdfplumber 표본 대조와 한계
- [mcp-offline-verification-2026-11-03.md](mcp-offline-verification-2026-11-03.md) — DB 없이 수행한 MCP·PDF·회로 표본 점검 기록
- [mcp-tool-candidates-draft.md](mcp-tool-candidates-draft.md) — MCP 도구 후보와 웹 검색 공급자 후보 조사, 비교 실측 해석
- [mcp-tool-contract-review.md](mcp-tool-contract-review.md) — MCP 검색 도구와 LangGraph 검색기의 연결 계약
- [mcp-tool-implementation-plan.md](mcp-tool-implementation-plan.md) — MCP 서버 도구 6종: 계약, 사용처, 구현 상태
- [tsc-public-part-verification-options.md](tsc-public-part-verification-options.md) — 코퍼스 밖 공개 품번 확인 정책 선택지
- [web-search-filter-comparison.md](web-search-filter-comparison.md) — 웹 검색 TSC 필터 유무 비교 실측 기록
- [web-search-results-interpretation.md](web-search-results-interpretation.md) — 웹 검색 비교 결과 지표 해석과 한계
- [embedding-grid-eval-2026-11-02.md](embedding-grid-eval-2026-11-02.md) — 임베딩 6종 x 검색 방식 격자 본평가: 78칸 전체 표, 카드 임베딩 시간·비용, 단계별 시간, 사전 등록 #16 기대 대조
- [retrieval-layered-rerun-2026-11-03.md](retrieval-layered-rerun-2026-11-03.md) — 검색 조합 층별 재측정(질의 글·토큰화·임베딩 11종·리랭커)의 사전 등록, 기대 대조, 결과
- [bit-search-measurement-2026-11-03.md](bit-search-measurement-2026-11-03.md) — 비트 후보 + pgvector 재정렬의 시간·recall@50·최종 점수 확인
- [retrieval-baseline-analysis.md](retrieval-baseline-analysis.md) — 동결 v1(`dataset_v1.jsonl`) 검색 베이스라인 3방식(`dense`·`bm25`·`hybrid`) 19문항 대조, 회귀 문항 및 실패 유형 4가지 분석, 채점 산식·한계 기록
- [evidence/](evidence/EVIDENCE.md) — 시장 근거 원자료 복사본(`docs/TOPIC.md` 각주 [1]·[2]·[4]). 목록과 해시는 `evidence/EVIDENCE.md`
- [demand-evidence-pricing-2026-11-16.md](demand-evidence-pricing-2026-11-16.md) — 수요 근거(채용공고·공시·도입 금액·단종정보 도구 구매계약)와 유사 서비스 공개 가격(심태현 조사, 2026-11-16). 간접 근거이며 SojaFit 구매 수요의 직접 입증은 아님
- [market-user-journey.md](market-user-journey.md) — 문제와 시장 근거: 관련 채용 역할 50건의 원문 링크와 반복 업무·역량, 사용자·지불 주체 사실/가설 구분, 페르소나 2종, 6단계 고객 여정 맵, 범용 챗봇 비교 항목, 외부 검토 계획(미수행)
- [grade-evidence-validation.md](grade-evidence-validation.md) — 1등급 2등급 3등급 근거 흐름과 검증 범위: 동작, 상한, 코드 위치, 원시 없는 측정

## 이 폴더 밖의 원본
- Codex v3-50 비교 원본(이 폴더에 두지 않음): `evals/guides/v3_50_codex_paste.md` · `evals/results/graph/2026-11-12-codex-v3-50/codex_answers.md` (EVAL_REPORT §10)
