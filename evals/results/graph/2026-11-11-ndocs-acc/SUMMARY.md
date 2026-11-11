# FIND_N_DOCS 정확도 (v3 50×1, GATE_WARMUP=1)

| n_docs | pass | mean | p50 | p95 | max | metrics |
|---:|---:|---:|---:|---:|---:|---|
| 10 | 37/50 | 4.12 | 4.4 | 9.8 | 13.8 | {'cited_gold': 25, 'correct_refusal': 12, None: 13} |
| 5 | 50/50 | 4.25 | 4.7 | 9.2 | 15.5 | {'cited_gold': 25, 'correct_refusal': 25} |
| 3 | 50/50 | 4.51 | 4.6 | 10.6 | 13.6 | {'cited_gold': 25, 'correct_refusal': 25} |

## 유형별 pass

| n_docs | Spec(candidate_*) | 기타 relevant | irrelevant |
|---:|---|---|---|
| 10 | 15/15 {'cited_gold': 15} | 10/10 {'cited_gold': 10} | 12/25 {'correct_refusal': 12, None: 13} |
| 5 | 15/15 {'cited_gold': 15} | 10/10 {'cited_gold': 10} | 25/25 {'correct_refusal': 25} |
| 3 | 15/15 {'cited_gold': 15} | 10/10 {'cited_gold': 10} | 25/25 {'correct_refusal': 25} |

## 실패 문항

- n10: [('v3-38', None, 'irrelevant', None), ('v3-39', None, 'irrelevant', None), ('v3-40', None, 'irrelevant', None), ('v3-41', None, 'irrelevant', None), ('v3-42', None, 'irrelevant', None), ('v3-43', None, 'irrelevant', None), ('v3-44', None, 'irrelevant', None), ('v3-45', None, 'irrelevant', None), ('v3-46', None, 'irrelevant', None), ('v3-47', None, 'irrelevant', None), ('v3-48', None, 'irrelevant', None), ('v3-49', None, 'irrelevant', None), ('v3-50', None, 'irrelevant', None)]
- n5: 없음
- n3: 없음

## Spec 문항별

| id | type | n10 | n5 | n3 |
|---|---|---|---|---|
| v3-01 | candidate_judge | PASS · cited_gold · 6.2s | PASS · cited_gold · 6.2s | PASS · cited_gold · 6.6s |
| v3-02 | candidate_judge | PASS · cited_gold · 6.5s | PASS · cited_gold · 5.8s | PASS · cited_gold · 5.9s |
| v3-03 | candidate_judge | PASS · cited_gold · 6.0s | PASS · cited_gold · 5.7s | PASS · cited_gold · 6.2s |
| v3-04 | candidate_judge | PASS · cited_gold · 4.9s | PASS · cited_gold · 4.8s | PASS · cited_gold · 4.7s |
| v3-05 | candidate_judge | PASS · cited_gold · 5.9s | PASS · cited_gold · 5.7s | PASS · cited_gold · 5.6s |
| v3-06 | candidate_judge | PASS · cited_gold · 8.9s | PASS · cited_gold · 8.8s | PASS · cited_gold · 8.2s |
| v3-07 | candidate_judge | PASS · cited_gold · 5.1s | PASS · cited_gold · 6.1s | PASS · cited_gold · 5.3s |
| v3-08 | candidate_judge | PASS · cited_gold · 5.3s | PASS · cited_gold · 6.5s | PASS · cited_gold · 8.1s |
| v3-09 | candidate_judge | PASS · cited_gold · 6.9s | PASS · cited_gold · 7.1s | PASS · cited_gold · 7.1s |
| v3-10 | candidate_judge | PASS · cited_gold · 5.7s | PASS · cited_gold · 6.2s | PASS · cited_gold · 6.4s |
| v3-11 | candidate_find | PASS · cited_gold · 7.1s | PASS · cited_gold · 6.0s | PASS · cited_gold · 6.1s |
| v3-12 | candidate_find | PASS · cited_gold · 7.3s | PASS · cited_gold · 5.5s | PASS · cited_gold · 6.5s |
| v3-13 | candidate_find | PASS · cited_gold · 7.4s | PASS · cited_gold · 7.2s | PASS · cited_gold · 7.1s |
| v3-14 | candidate_find | PASS · cited_gold · 5.7s | PASS · cited_gold · 6.5s | PASS · cited_gold · 4.9s |
| v3-15 | candidate_find | PASS · cited_gold · 10.6s | PASS · cited_gold · 9.2s | PASS · cited_gold · 9.0s |

## Spec verdict 차이

- v3-11: n10=[['GS1G', 'ROLE_SUFFICIENT'], ['GS1J', 'ROLE_SUFFICIENT'], ['S1G-K', 'ROLE_SUFFICIENT']] · n5=[['GS1G', 'ROLE_SUFFICIENT'], ['GS1J', 'ROLE_SUFFICIENT'], ['S1G-K', 'ROLE_SUFFICIENT']] · n3=[['GS1G', 'ROLE_SUFFICIENT'], ['GS1J', 'ROLE_SUFFICIENT'], ['S1GH', 'ROLE_SUFFICIENT']]
- v3-12: n10=[['HER105G', 'ROLE_SUFFICIENT'], ['HER105G-K', 'ROLE_SUFFICIENT'], ['HER105GH', 'ROLE_SUFFICIENT']] · n5=[['HER105G', 'ROLE_SUFFICIENT'], ['HER105G-K', 'ROLE_SUFFICIENT'], ['HER105GH', 'ROLE_SUFFICIENT']] · n3=[['HER105G', 'ROLE_SUFFICIENT'], ['HER105GH', 'ROLE_SUFFICIENT'], ['HER106G', 'ROLE_SUFFICIENT']]

## 판정
- n10: pass 37/50, Spec 15/15 {'cited_gold': 15}, p95 9.8
- n5: pass 50/50, Spec 15/15 {'cited_gold': 15}, p95 9.2
- n3: pass 50/50, Spec 15/15 {'cited_gold': 15}, p95 10.6
- **n5가 정확도에서 최상위(동률 포함)**. 기본 5 유지.
