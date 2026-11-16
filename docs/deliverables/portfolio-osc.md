# 포트폴리오 1장 — 오세창

> 초안 — 본인 확인 필요(작성: 조장 위임 AI, 2026-11-17). 기준 커밋 `799ae636`(main). 저장소의 작업 기록 · 커밋 · PR · 결과 파일에 있는 사실만 옮겼다.

제출물. 채용 담당자가 1분 안에 읽는 분량. `EVAL_REPORT.md` · `docs/GATES.md`에 있는 숫자를 먼저 쓰고, 그 밖의 숫자는 근거 경로를 붙이고 "EVAL 밖"으로 표시했다.

## 프로젝트 한 줄

소형 MCU 회로의 다이오드를 바꿀 때, KiCad 넷리스트에서 역할을 읽고 후보마다 TSC 데이터시트 쪽·표·행을 근거로 판정하는 RAG 멀티 에이전트(SojaFit).

## 내가 맡은 부분

| 항목 | 내용 |
|---|---|
| 맡은 축 | 검색·데이터(`README.md` 7절). Supervisor 모델 비교, 청킹 v4h, 내부 근거가 모자랄 때의 제조사 공식 PDF 근거(2 · 3등급), 원본 회로도 검색, 작업대 화면, Docker 기동 측정 |
| 내가 만든 것 | Supervisor 후보 6종 3차 비교와 결과 보존, Supervisor 프롬프트 V0 결과의 Langfuse Dataset · Experiment 적재, 청킹 v4h(pdfplumber 표 칸 우선)와 문서 분류 열, 공식 PDF 표 행 인용과 1→2→3등급 근거 폴백, 공개 · 제조사 공식 원본 회로도 검색과 PNG 변환, 작업대 UI, Docker 첫 응답 실측 |
| 커밋·PR | 작업 브랜치 `OSC`, `OSC-chunk`. main `799ae636` 기준 커밋 164건(병합 커밋 제외, 작성자 `OSC` · `sechang405-maker`), 병합된 PR 30건(10-30 #6 ~ 11-16 #146). 묶음 예: #55(Supervisor 3차), #70(청킹 v4h), #103(1→2→3등급 근거), #146(공식 2등급 확장 · 회로도 후보 선택). 상세는 `docs/worklog/osc.md` |

## 숫자로 보이는 결과

- 검색·청킹: 현재 서비스 청커는 PR #70의 `tsc-v4h-2026-11-08`이다(EVAL 1장 맨 위 표 "현재 청킹 구현"). v1 청커와 바꿔 잰 v3 검색 21문항 Recall@5는 v1 · v4h 모두 **0.8095**로 같았다(EVAL 12장 표, `evals/results/chunking/v1-vs-v4h-2026-11-13/`). 개선 수치로 쓰지 않는다.
- 멀티 에이전트(Supervisor 모델 비교, EVAL 밖): 동결 v2 70문항, 후보 6종 × 3차. 3차는 420행 · 855호출 · 보고 비용 US$0.239. 질문 유형 정답(35문항)은 Luna · Jev **33/35**, Haiku 23/35. 최종 후보 3종(순위 없음)만 남겼다(`docs/research/supervisor-stage3-results.md`, `evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json`). 서비스 Supervisor의 Haiku 채택은 이 비교가 아니라 ADR 0017의 결정이다.
- 관측(Langfuse, EVAL 밖): Supervisor 프롬프트 V0 13문항 × 후보 3종 결과를 모델 재호출 없이 Dataset **13항목 · Experiment 3개 · 점수 273개**로 적재하고, API 재조회 합계가 로컬 결과와 같음을 확인했다(`docs/worklog/osc.md` 182 ~ 189행, `evals/results/supervisor/2026-11-06-prompt-v0-v1/langfuse_import.json`).
- LangGraph 중단·재개(EVAL 밖): 재개 실행 1건에서 Exa 2회 · 공식 PDF 2건 · 노드 응답 5회(Supervisor 2 · 판정 조건 읽기 1 · 문서 답변 2)로, 품번별 PDF 행(W1 50 V, W2 40 V)이 저장 답변과 재조회에서 같게 남았다(`docs/worklog/osc.md` 723 ~ 728행).
- 기동(EVAL 밖, `docs/research/docker-cold-start-measurements.md`): 빈 Docker에서 `docker compose up` → 첫 `/health` 3회 중앙값 **114.159초**(600초 이내). Cloud Run 최소 인스턴스 0 → 1에서 유휴 뒤 첫 응답 **14.498 → 0.324초**(각 1회). 비용 때문에 0대로 되돌렸다.

## 내가 내린 판단과 그 이유

- **Supervisor 후보에 순위를 매기지 않았다**: `deepseek-v4.1-flash`는 형식 통과가 2차 62/70에서 3차 7/70으로 떨어졌는데 공급자 변경과 출력 256토큰 잘림이 겹쳐 원인을 모델로 정하지 않았다. 이 모델과 `command-a-plus` · `muse-glimmer-30b`는 후보에서 뺐다(`docs/worklog/osc.md` 411 ~ 430행).
- **원시가 없는 수치는 제출 보고서에서 내렸다**: PR #27 검토 뒤, 저장소에 원시 결과가 없는 임베딩 확장 평가의 Recall@5 · MRR을 `EVAL_REPORT.md`에서 빼고 조사 문서에만 남겼다(`docs/worklog/osc.md` 254 ~ 258행).
- **KiCad 분리 · 병렬 설치를 버렸다**: 분리하면 API 이미지가 41.77% 줄지만 첫 `/health`는 109.37 → 110.58초로 줄지 않았고, 병렬 설치는 2.782초 더 느렸다(`docker-cold-start-measurements.md` 1절 · 맨 위 표).
- **PDF 숫자는 모델 글이 아니라 표 칸으로 문장을 만든다**: 원문이 40 V인데 모델이 쓴 400 V [W1]이 검사를 통과하던 구현을, 모델은 행만 고르고(`pdf_rows`) 서버가 PDF 칸의 품번 · 값 · 단위로 문장을 만들게 바꿨다. 시험은 400 V · 다른 품번 · 다른 단위를 거절한다(`docs/worklog/osc.md` 709 ~ 713행).

## 배포 주소와 저장소

- API: README 맨 위 Cloud Run `/health`(평가용 계정·비밀번호는 적지 않음).
- 저장소: 팀 비공개 `aihuman-7th/proj3-b`.
