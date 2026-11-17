# deliverables

## 역할
- 이 폴더: 최종 제출 문서의 양식과 본문을 둡니다(과제 가이드 G7).
- 넣는 것: AI 코딩 도구 사용 기록, 실패 사례 분석, 시연 영상 스크립트와 영상 파일(`video/`), 포트폴리오, Langfuse 화면 캡처, 발표 자료(`presentation/`). 문서마다 첫머리 헤더(상태, 기준일, 기준 커밋, 정본 여부, 관련 문서)를 둡니다.
- 넣지 않는 것: 평가 리포트(루트 `../../EVAL_REPORT.md`), 게이트 증거(`../GATES.md`), 배포 주소(루트 `../../README.md` 맨 위), 조원별 작업 기록(`../worklog/`).
- 담당: 평가·문서

## 파일

| 파일 | 유형 | 한 줄 설명 |
|---|---|---|
| `ai_tools_log.md` | 제출물 | AI 코딩 도구 사용 기록과 검증 방법, 도구가 틀린 곳 |
| `failure_analysis.md` | 제출물 | 실패 사례 분석: 증상, 원인, 확인 방법, 조치, 못 고친 것 |
| `demo_script.md` | 제출물 | 시연 영상 촬영 스크립트 |
| `portfolio.md` | 제출물 양식 | 포트폴리오 1장 양식. 조원마다 `portfolio-{이름}.md`로 복사 |
| `portfolio-jeongun.md` | 제출물 | 하정운 포트폴리오 |
| `portfolio-osc.md` | 제출물 | 오세창 포트폴리오 초안(11-17 조장이 작업 기록에서 옮겨 작성, 본인 확인 필요) |
| `portfolio-sth.md` | 제출물 | 심태현 포트폴리오 초안(11-17 조장이 작업 기록에서 옮겨 작성, 본인 확인 필요) |
| `submission_checklist.md` | 제출물 | 제출 체크리스트: 게이트·제출물 항목별 증거 경로와 상태 |
| `langfuse/` | 제출물 | Langfuse 스크린샷 7장: 01~03 목록 · 트레이스 상세 · 비용(11-13 배포본), 04~07 점수 칩이 붙은 평가 trace 상세 · 그 trace의 점수 탭(13개) · 점수 목록 · 홈 대시보드(11-17 운영 프로젝트 SojaFit_v2). 설명은 아래 "Langfuse 스크린샷" 절 |
| `video/` | 제출물 | 시연 영상 `sojafit-demo-2026-11-17.mp4`(1분 35초, 1280×720). 정상 경로 v3-01(조건 질문 정지 → 재개 → 역할상 충분 판정 · 근거 → 승인 → 견적 → 대체 검토 보고서)과 실패 경로 3개(실측값 요청 · 코퍼스에 없는 품번 LL4149 · 프롬프트 인젝션), 화면마다 자막 한 문장. 첫 장면은 배포 `/health`와 리비전 `sojafit-api-main-28b14600-1117` 로그인 화면, 나머지는 같은 코드(main `28b14600`)의 로컬 실제 모드(실제 모델) |
| `presentation/` | 제출물 | 최종 발표 덱(`sojafit-final-2026-11-18.pptx`)과 슬라이드 · 발표자 · 수치 근거 표. [PRESENTATION.md](presentation/PRESENTATION.md) |

## 남은 일

가이드(과제 가이드 G6, G7과 일정 D11, D12 마감)가 요구하는 항목과 지금 상태다(2026-11-17 갱신).

| 항목 | 요구 | 현재 | 마감 |
|---|---|---|---|
| 시연 영상 | 3분 이내, 정상 경로와 실패 경로. 시연 영상 원본과 동결 시점 커밋 SHA, 배포 리비전 번호 | 11-17 생김: `video/sojafit-demo-2026-11-17.mp4`, 1:35. 정상 경로 v3-01과 실패 사례 3건, 화면마다 자막 1줄. main `28b14600`과 같은 코드를 로컬 실제 모드로 녹화했고, 첫 화면은 배포본 `/health`와 리비전 `sojafit-api-main-28b14600-1117`의 로그인 화면이다. 동결 시점 커밋 `9c87ba36`. 스크립트는 `demo_script.md`. 파일은 다른 작업이 이 경로에 넣는다(이 커밋에는 아직 없음) | D11 11/16 |
| Langfuse 스크린샷 | 3장 이상, 트레이스 상세 1장 이상 | 7장. 11-13 배포본 3장(목록, 트레이스 상세, 비용)과 11-17 4장(점수가 붙은 트레이스 상세, 트레이스 점수 탭, 점수 목록, 홈 대시보드). 아래 "Langfuse 스크린샷" 절 | |
| 포트폴리오 | 조원 수만큼(LangGraph, 멀티에이전트, 평가, 관측의 수치 포함) | 조원 3명(`README.md` 7절) 모두 있음. `portfolio-osc.md` · `portfolio-sth.md`는 11-17 조장이 작업 기록 · 커밋 · PR · 결과 파일에서 옮긴 초안이다. 남음: 두 사람의 본인 확인. 두 초안의 일부 수치는 `EVAL_REPORT.md` 밖(작업 기록 · 연구 문서)이라 근거 경로를 붙이고 "EVAL 밖"으로 표시했다(양식 `portfolio.md`의 "EVAL_REPORT 숫자만" 규칙과 다름) | D12 11/17 |
| 발표 자료 | 전원 파트 분담 | 덱 20장: [presentation/](presentation/PRESENTATION.md)(11-17). 발표자 배정은 README 7절 역할 기준 초안 | D12 11/17 |
| 제출 체크리스트 | 최종 제출 때 확인 | 초안 있음: [submission_checklist.md](submission_checklist.md)(2026-11-13). 가이드 원문 사본이 저장소에 없어 `GATES.md` · 이 문서의 요구만 담음 | D12 11/17 |
| `failure_analysis.md` 보강 | 코드로 되돌린 결정 1건과 이유, 미채택 실험, 판정자 한계 | 11-13 채움: 되돌린 결정(#46), 미채택 실험 4건, 판정자·도구 한계. 11-16 채움: 인젝션 사례 1건(C2 수정 전)과 Luna 한계(파일 9절, 판정을 사람과 대조한 기록은 없음). 11-17 정리: 정답 초안 작성자 서술(파일 8절). 현재 서술은 모두 "초안 Codex(하정운 검수) · 1차 심태현 · 최종 하정운"이고, 심태현을 초안 작성자로 적은 줄은 없다. ADR 0015만 "2차 판정"으로 적었다(같은 뜻). 근거가 11-13 기록 하나뿐인 한계는 남음 | D12 11/17 |
| `ai_tools_log.md` 보강 | 팀의 AI 코딩 도구 사용 기록 | 11-13 Claude 행. 11-17 추가: 심태현 행(Codex), 오세창 행(도구 이름이 기록에 없음), 하정운 11-17 Claude Code 행. 남음: 두 조원 본인 확인, 김재훈 행 없음(11-06 탈퇴), citation-check 브랜치 확인(후보 커밋 `bfdb77ab`) | D12 11/17 |
| 개인정보·비밀값 점검 | 포트폴리오와 스크린샷에 개인정보나 비밀값이 없는지 | 2026-11-13 1차 점검: `docs/deliverables/**` 마크다운 · 스크린샷 3장(이미지로 열어 확인) · 11-13 새 파일(`evals/results/d10/` 새 파일, TALLY 폴더, `v3_judging_record.md`, 스크립트 2개)에서 개인 이메일 · 전화번호 · API 키/토큰 형식 · 절대 경로를 검색. 이메일 · 전화번호 · 키 0건. 절대 경로 1건: `evals/results/d10/pytest_full_2026-11-13.txt` 9행(로컬 사용자 이름이 든 저장소 경로, 로그 원본이라 고치지 않음, 제출 전 삭제 또는 마스킹 판단 필요). 스크린샷 왼쪽 아래에 계정 표시명 `DNS`가 보임, 사용자별 비용 칸에 숫자 사용자 ID 1 · 2 · 4 · 16, 입출력은 `[redacted]`. 포트폴리오 최종본은 점검 전. 11-17: 새 포트폴리오 2장과 `ai_tools_log.md` 새 행은 이름 · GitHub id · 역할만 쓰고 이메일 · 로컬 경로 · Langfuse 프로젝트 ID · 트레이스 주소를 넣지 않았다(문자열 검색으로 확인). 11-17 스크린샷 4장은 이미지로 열어 확인: 비밀값 없음, 왼쪽 아래 계정 표시명 `DNS`, `04`에 동결 v3 문항 글이 마스킹 없이 보임(평가 문항, 개인정보 아님). 영상은 점검 전 | D12 11/17 |
| 배포 유지 | 발표일까지 배포 유지, 제출 링크·경로·발표 시각 | 확인 기록 없음 | 발표 11/18 |
| 배포본 25단계 실행(평가용 계정) | 제출 직전 배포본에서 평가용 계정 A · B로 승인 · 견적 · 계정 격리 확인 | 하지 않음. 평가용 계정 비밀번호가 필요해 사람만 한다(지난 통과 기록은 `GATES.md` G1, 리비전 `574de79-rs`) | D12 11/17 |
| 평가용 계정 제출 | 평가용 계정을 비공개로 제출 | 하지 않음. 사람만 한다. 저장소 · 문서에 계정과 비밀번호를 적지 않는다 | D12 11/17 |

## Langfuse 스크린샷

`01` ~ `03`은 2026-11-13 10:13~10:15 KST에 캡처했다. 프로젝트 `SojaFit_v2`(EU `cloud.langfuse.com`), 조회 범위 최근 1일. 배포 리비전 `sojafit-api-fadde2a`가 보낸 트레이스(환경 `default`, 태그 `analysis` `live`)다. 입력과 출력은 서비스가 `[redacted]`로 가려 보낸다.

| 파일 | 장면 | 보이는 것 |
|---|---|---|
| [`langfuse/01-trace-list.jpg`](langfuse/01-trace-list.jpg) | 트레이스 목록(루트 관측, 환경 `default`) | 11-13 09:38~10:10 배포본 요청이 트레이스로 들어옴(최근 1일 루트 관측 약 101건, `LangGraph`와 `analysis-metadata` 포함), 입출력 마스킹 |
| [`langfuse/02-model-call-detail.jpg`](langfuse/02-model-call-detail.jpg) | 트레이스 `ce5f5ad0…` 타임라인과 모델 호출 상세 | Spec 에이전트(대체 부품 판정, LLM 2회) → Supervisor 재계획 → RAG 에이전트(LLM 1회)가 나뉘어 보이고, 선택한 RAG 호출의 모델 `anthropic/claude-haiku-5.5`, 4.76초, 5k 토큰, 0.001달러 |
| [`langfuse/03-cost-dashboard.jpg`](langfuse/03-cost-dashboard.jpg) | Langfuse Cost Dashboard(환경 `default`+`eval`) | 최근 1일 트레이스 151건, 비용 합계 0.118649달러, 모델별·환경별·사용자별 비용 |
| [`langfuse/04-trace-detail-scores-header.jpg`](langfuse/04-trace-detail-scores-header.jpg) | 트레이스 `gate v3-47` 상세(11-17, 화면 시각 03:33:45, 10.44초) | 머리에 점수 칩(passed_cards · latency_s · tries · question_type · refusal_code · cost_usd 외 10개), 노드 트리(입력 읽기 → 기억 읽기 → 품번·판 확인 → Supervisor → RAG 에이전트 → 답 모으기 → 거절), 평가 문항 입력 · 출력(마스킹 없음) |
| [`langfuse/05-trace-scores-tab.jpg`](langfuse/05-trace-scores-tab.jpg) | 같은 트레이스의 Scores 탭(11-17) | 점수 13개: refusal_code, latency_s, docs_found, pass, question_type, cost_usd, tries, path, answer_metric, llm_calls, hops, not_found, passed_cards |
| [`langfuse/06-scores-list.jpg`](langfuse/06-scores-list.jpg) | Scores 목록(11-17, 최근 1일) | gate 실행 트레이스마다 붙은 점수 행(화면 시각 03:34), 446쪽(쪽당 50행) |
| [`langfuse/07-home-dashboard-2026-11-17.jpg`](langfuse/07-home-dashboard-2026-11-17.jpg) | 홈 대시보드(11-17, 환경 `eval` · `default`, 최근 1일) | 트레이스 1.68K, 비용 $1.17(모두 `anthropic/claude-haiku-5.5`, 26.25M 토큰), 점수 22.25K, 관측 30.76K |

- `02`의 트레이스는 마지막 노드가 `거절`이다. 판정 근거가 모자라 거절로 끝난 질문이고, 이 장은 에이전트 구조와 호출 기록을 보이려고 골랐다.
- 403 원인과 해소 기록은 [evals/results/d10/langfuse_403_2026-11-13.md](../../evals/results/d10/langfuse_403_2026-11-13.md).
- `04` ~ `07`은 2026-11-17에 캡처했다(프로젝트 `SojaFit_v2`). 파일은 다른 작업이 이 폴더에 넣는다(이 커밋에는 아직 없음). 위 칸은 작업 폴더의 같은 이름 파일을 열어 옮겼다. 트레이스를 보낸 실행의 소스 커밋은 화면에 없다.
