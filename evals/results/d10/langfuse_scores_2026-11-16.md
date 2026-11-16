# Langfuse 트레이스에 붙은 평가 점수 (2026-11-16)

G6 증거. 강사 11/13 · 11/16 코멘트 ④ "Langfuse 화면에서 평가 점수가 트레이스에 붙어 보이지 않고"에 대한 기록이다. 평가 실행기(`evals/runners/run_gate.py` 137행 `client.create_score(trace_id=…)`)는 문항마다 점수를 그 문항의 트레이스에 올린다. 그 점수가 실제로 트레이스에 붙어 있는지 Langfuse 공개 API로 읽었다.

## 결과 [실측, 2026-11-16 09:5x KST]

- 프로젝트: `SojaFit_v2`(`cmwadynwy063mad0eyrziwgqt`). 키는 운영 서비스와 같은 Secret Manager 값(출력 · 파일에 남기지 않음)
- 대상 트레이스: `7bb6b3d98274e748aa1ea89555cb4d0e` = 동결 v3 웹 끔 측정(`evals/results/graph/2026-11-16-speedoff-baseline/B3/set1.json`, 세션 `gate-dataset_v3-1115-1438-set1`)의 **v3-01** 문항. 결과 파일의 `trace_url`이 이 트레이스를 가리킨다
- 읽은 API: `GET /api/public/v3/scores?traceId=…`(점수), `GET /api/public/v2/observations?traceId=…`(같은 트레이스의 관측, `environment`=`eval`)
- 이 트레이스에 붙은 점수 **15개**: 결과 파일의 같은 문항 값과 같다(`pass`=True, `answer_metric`=`cited_gold`, `latency_s`=6.4)

| 점수 이름 | 값 | 형식 |
|---|---|---|
| `pass` | True | BOOLEAN |
| `answer_metric` | cited_gold | CATEGORICAL |
| `question_type` | candidate_judge | CATEGORICAL |
| `path` | 입력 읽기>기억 읽기>사실 확인>계획>판정 읽기>판정>모으기>답 정리>답 검사>끝 | CATEGORICAL |
| `latency_s` | 6.4 | NUMERIC |
| `llm_calls` · `hops` · `tries` | 2 · 1 · 0 | NUMERIC |
| `cost_usd` | 0.00085807 | NUMERIC |
| `fake_citations` · `uncited_sentences` | 0 · 2 | NUMERIC |
| `docs_found` · `passed_cards` | 0 · 0 | NUMERIC |
| `not_found` | False | BOOLEAN |
| `refusal_code` | (빈 값) | CATEGORICAL |

원본 응답(점수 15개, 관측 1개): [langfuse_scores_2026-11-16.json](langfuse_scores_2026-11-16.json)

## 화면에서 보는 법

Langfuse → `SojaFit_v2` → Traces → 위 트레이스 id 검색(또는 결과 파일의 `trace_url`) → 오른쪽 Scores 칸. 또는 Sessions → `gate-dataset_v3-1115-1438-set1`에서 문항 50개 트레이스의 `pass` 점수를 함께 본다.

## 참고: Langfuse Cloud 옛 공개 API 제거 (2026-11-16)

같은 조회에서 옛 읽기 API(`GET /api/public/scores`, `/api/public/traces`, `/api/public/sessions`)가 410 Gone을 돌려줬다. 응답은 2026-11-16에 제거됐다며 `/api/public/v3/scores` · `/api/public/v2/observations`를 쓰라고 안내한다. 저장소 코드(`backend` · `scripts` · `evals`)는 이 옛 읽기 API를 부르지 않는다(`git grep` 0건). 점수 쓰기(`create_score`, SDK 5.0.4)는 11-15 23:38 KST까지 들어온 것을 위 조회로 확인했고, 11-16 제거 뒤의 쓰기는 확인하지 않았다.

## 한계

- 대시보드 화면 캡처는 이 기록을 쓸 때 없다(브라우저 로그인 필요). API로 읽은 값이다.
