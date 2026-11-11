# A–D 실험 실측 (기본값 변경 없음, GATE_WARMUP=1)

| 실험 | baseline pass | exp pass | base mean/p95 | exp mean/p95 | 실패 변화 | 판정 |
|---|---|---|---|---|---|---|
| A SUPERVISOR_REPLAN off | 9/9 | 9/9 | 8.32/10.1 | 9.48/14.9 | base[]→exp[] | 보류/폐기(속도만 또는 혼재) |

### A 문항

| id | base_s | exp_s | base_ok | exp_ok |
|---|---:|---:|---|---|
| v3-01 | 8.2 | 9.9 | True | True |
| v3-03 | 9.0 | 8.9 | True | True |
| v3-16 | 8.2 | 7.9 | True | True |
| v3-20 | 6.6 | 14.0 | True | True |
| v3-21 | 9.8 | 9.2 | True | True |
| v3-24 | 7.4 | 7.4 | True | True |
| v3-25 | 9.8 | 6.6 | True | True |
| v3-41 | 5.8 | 6.5 | True | True |
| v3-15 | 10.1 | 14.9 | True | True |
| B DOCS_MAX_SEARCHES=1 | 6/6 | 6/6 | 10.15/13.8 | 8.18/12.0 | base[]→exp[] | 채택검토(정확도유지·속도↑) |

### B 문항

| id | base_s | exp_s | base_ok | exp_ok |
|---|---:|---:|---|---|
| v3-16 | 13.3 | 12.0 | True | True |
| v3-20 | 13.8 | 11.2 | True | True |
| v3-21 | 10.9 | 8.6 | True | True |
| v3-24 | 4.0 | 4.1 | True | True |
| v3-25 | 8.8 | 3.6 | True | True |
| v3-41 | 10.1 | 9.6 | True | True |
| C FIND_N_DOCS=3 | 7/7 | 7/7 | 7.66/15.3 | 7.61/10.9 | base[]→exp[] | 보류(차이 미미) |

### C 문항

| id | base_s | exp_s | base_ok | exp_ok |
|---|---:|---:|---|---|
| v3-01 | 6.1 | 6.0 | True | True |
| v3-03 | 6.1 | 5.8 | True | True |
| v3-15 | 15.3 | 9.0 | True | True |
| v3-11 | 6.3 | 5.9 | True | True |
| v3-12 | 7.4 | 8.2 | True | True |
| v3-13 | 5.9 | 7.5 | True | True |
| v3-14 | 6.5 | 10.9 | True | True |
| D JUDGE_NEAR_FIND=0 | 6/7 | 7/7 | 8.19/13.2 | 8.76/16.8 | base['v3-15']→exp[] | 보류/폐기(속도만 또는 혼재) |

### D 문항

| id | base_s | exp_s | base_ok | exp_ok |
|---|---:|---:|---|---|
| v3-01 | 8.9 | 10.4 | True | True |
| v3-03 | 8.2 | 8.3 | True | True |
| v3-15 | 13.2 | 16.8 | False | True |
| v3-11 | 5.7 | 6.0 | True | True |
| v3-12 | 7.3 | 7.1 | True | True |
| v3-13 | 7.4 | 6.2 | True | True |
| v3-14 | 6.6 | 6.5 | True | True |

fail metrics base={'v3-15': 'over_refusal'} exp={}

## 공통
- 기본값(코드·env 기본)은 바꾸지 않음. FIND_N_DOCS 실험 기본은 이미 5.
- E(v3 50×1)는 이어서 측정.

## E v3 50×1 (GATE_WARMUP=1 FIND_N_DOCS=5, 측정만)

- pass 50/50
- mean 4.25 · p50 4.7 · p95 9.2 · max 15.5
- metrics: {'cited_gold': 25, 'correct_refusal': 25}
- fails: []

## 최종 판정 (기본값 변경 없음)

| 실험 | 판정 | 이유 |
|---|---|---|
| A SUPERVISOR_REPLAN=0 | **폐기** | 9/9 동일, mean·p95 오히려 ↑ |
| B DOCS_MAX_SEARCHES=1 | **기본 유지** (#49 위험) | 이번 6/6·속도↑이나 표본 작음 |
| C FIND_N_DOCS=3 | **보류** (5 유지) | 7/7, 평균 차이 미미 |
| D JUDGE_NEAR_FIND=0 | **기본 유지** | 정확도 7/7로 회복했으나 mean·p95 ↑ |
| E | 기준선 기록 | 위 숫자 |
