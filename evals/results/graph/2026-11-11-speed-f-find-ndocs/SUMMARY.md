# F1 FIND_N_DOCS (GATE_WARMUP=1, Spec 7문항)

| id | n10 | n5 | d | pass10 | pass5 | find_max10 | find_max5 |
|---|---:|---:|---:|---|---|---:|---:|
| v3-01 | 6.5 | 6.7 | +0.2 | True | True | 0 | 0 |
| v3-03 | 6.9 | 5.5 | -1.4 | True | True | 0 | 0 |
| v3-15 | 10.4 | 9.9 | -0.5 | True | True | 5775 | 5084 |
| v3-11 | 7.0 | 6.0 | -1.0 | True | True | 564 | 548 |
| v3-12 | 8.0 | 7.9 | -0.1 | True | True | 607 | 705 |
| v3-13 | 7.4 | 6.0 | -1.4 | True | True | 1694 | 1216 |
| v3-14 | 6.3 | 6.7 | +0.4 | True | True | 621 | 869 |

- A n10: 7/7, mean 7.5, p50 7.0, p95 10.4
- B n5: 7/7, mean 7.0, p50 6.7, p95 9.9
- 판정: **채택** FIND_N_DOCS=5 (정확도 동일 7/7·cited_gold, 평균·p95 소폭↓). 기본값을 5로 바꾸고 mixed로 재확인.

## F2 mixed 확인 (FIND_N_DOCS=5 vs E0 n10)

- E0: pass 8/9 mean 10.89 p50 9.6 p95 28.4
- F2: pass 8/9 mean 8.23 p50 8.6 p95 11.4
- F2 실패: ['v3-20']
