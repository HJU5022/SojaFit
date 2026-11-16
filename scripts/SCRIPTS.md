# scripts

## 역할
- 이 폴더: 서비스 코드 밖에서 손으로 돌리는 측정·점검·운영 보조 스크립트와 그 원시 결과를 둔다. 저장소 루트에서 실행한다.
- 넣는 것: 평가셋 평가가 아닌 실측·점검·운영 스크립트(종류별 하위 폴더), 그 원시 결과(`results/`, 파일 이름은 `<무엇>_<YYYY-MM-DD>.json`). 이 폴더 바로 아래에는 파일을 두지 않는다.
- 넣지 않는 것: 서비스 코드(`backend/`), 평가셋 실행·동결 스크립트와 평가 결과(`evals/`, `evals/results/`), 측정 해석(`docs/`), 테스트(`tests/`).
- 담당: 각 모듈 담당

## 분류

각 스크립트를 호출 근거(`grep`으로 확인한 호출처)로 나눈다. 하위 폴더 설명 파일의 표에 같은 분류가 있다.

| 분류 | 기준 | 스크립트 |
|---|---|---|
| 운영 | 시험·CI·서비스 코드·운영 절차 문서가 호출하거나 지정하고, 지금 코드에서 돈다 | `db/gen_schema_docs.py`, `db/voyage_rollout.py`, `demo/record_demo.py`, `langfuse/langfuse_skill_check.py`, `smoke/http_smoke.py` |
| 재현용 | 저장소에 원시 결과가 있고, 결과를 다시 만들거나 구조를 증명하는 데 쓴다. 호출처는 문서·시험 | `auth/auth_boundary_after_merge.py`, `db/verify_chain/verify_chain.sh`, `db/verify_redesign/*.sh`, `eval/stage_report.py`, `eval/approval_wait_report.py`, `smoke/injection_http.py`, `bit_search/bit_search_exp.py` |
| 일회성 | 한 번 쓴 실험·변환이거나 전제(OS, 모델·차원, 외부 작업 폴더)가 지금 맞지 않아 그대로 돌지 않는다 | `auth/measure_scrypt_concurrent.py`, `eval/import_human_review.py`, `hf_jobs/hf_job.py`, `hf_jobs/hf_data.py`, `smoke/verify_external_schematics.py` |

호출 근거: `db/gen_schema_docs.py`는 `tests/db/test_schema_docs.py`가, `demo/record_demo.py replay`는 `.github/workflows/ci.yml`이, `langfuse/langfuse_skill_check.py`의 함수는 `tests/services/test_langfuse_prompts.py`가, `smoke/http_smoke.py`는 `tests/api/test_http_smoke.py`와 `docs/GATES.md`가 부른다. 나머지 근거는 하위 폴더 설명 파일의 "분류 근거" 열.

## 파일

| 폴더 | 내용 | 설명 파일 |
|---|---|---|
| `SCRIPTS.md` | 이 문서 | |
| `auth/` | 인증 실측 스크립트(잠금·만료 경계, scrypt 동시성) | [AUTH.md](auth/AUTH.md) |
| `bit_search/` | 비트 후보 + 정확 재정렬 검색 속도·recall 실험 스크립트 | [BIT_SEARCH.md](bit_search/BIT_SEARCH.md) |
| `db/` | DB 손 작업(voyage-4-large 적용 점검·마이그레이션·검증, 스키마 문서 생성) | [DB.md](db/DB.md) |
| `demo/` | 키 없는 데모가 재생할 LLM 응답을 실제 키로 기록하고 키 없이 재생해 대조 | [DEMO.md](demo/DEMO.md) |
| `eval/` | 사람 채점 시트를 평가 JSONL로 되돌리는 변환과, 단계별 응답 시간·비용·사람 대기 시간 집계(D8) | [EVAL.md](eval/EVAL.md) |
| `hf_jobs/` | Hugging Face Jobs로 GPU 임베딩을 돌리는 스크립트 | [HF_JOBS.md](hf_jobs/HF_JOBS.md) |
| `langfuse/` | Langfuse 프롬프트·Skill 연결 점검 스크립트 | [LANGFUSE.md](langfuse/LANGFUSE.md) |
| `smoke/` | 로컬 compose·배포 주소의 사용자 흐름을 HTTP로 점검하는 스크립트와 인젝션 HTTP 시험 | [SMOKE.md](smoke/SMOKE.md) |
| `results/` | 측정 원시 결과. 폴더 설명 파일 없이 아래 "결과 폴더"가 설명함. 평가 지표는 `evals/results/` | |

## 결과 폴더

`results/` 하위 폴더와 파일. 원시 파일은 수정하지 않는다.

| 폴더 | 파일 | 만든 스크립트 | 내용 |
|---|---|---|---|
| `results/smoke/` | `schematic_search_observations_2026-11-15.json` | 브라우저 직접 검증 기록 복사 | 로컬 8011의 회로도 후보·공개 원본 링크·이미지 로드 상태. 새 실측이나 평가 점수가 아님. 해석: [공유 보고서](../docs/research/frontend-schematic-work-summary-2026-11-15.md) |
| `results/auth/` | `auth_boundary_2026-11-02.json` | `auth/auth_boundary_after_merge.py` | 로그인 잠금·세션 만료 경계 실측 |
| `results/auth/` | `scrypt_concurrent_2026-11-02.json`, `scrypt_concurrent_2026-11-04.json` | `auth/measure_scrypt_concurrent.py` | 동시 scrypt·프로세스 메모리 실측 |
| `results/storage/` | `storage_contract_2026-11-02.json` | `backend/rag/storage.py` CLI 계열 | 합성 벡터 64행·1536차원으로 vector→halfvec 형식·용량·검색 계약 확인. 실제 코퍼스 결과 아님 |
| `results/hnsw/` | `hnsw_exp_{base,A_english,B_partfilter,C_kure,D_qwen}_2026-11-01.json` | 저장소 밖 `전자_데이터시트/evidence/hnsw_exp/` | 정확 검색 대 HNSW 비교 실험 5건, 19문항 Recall@5·MRR·지연 |
| `results/parser/` | `parser_accuracy_2026-11-01.json`, `parser_truth_2026-11-01.json`, `parser_speed_2026-11-01.jsonl` | 저장소 밖 | 도구별 행 적중, 정답표, 속도 |
| `results/parser/` | `parse_gpu_log_2026-11-01.jsonl`, `parse_gpu_recall_2026-11-01.json`, `parse_gpu_witness_unmatched_2026-11-01.json` | 저장소 밖 | 1,360건 GPU 파싱 로그, 표 숫자 재현율, 대조 못 한 값 목록 |
| `results/bit_search/` | `bit_search_2026-11-03.json`, `bit_search_final_2026-11-03.json`, `bit_search_warm_2026-11-03.json` | `bit_search/bit_search_exp.py` | 후보 수 N별 시간·recall@50, v1 관련 19문항 최종 점수 확인, 비트 검색만 이어서 잰 시간. 해석: [bit-search-measurement-2026-11-03.md](../docs/research/bit-search-measurement-2026-11-03.md) |
| `results/docker_performance/` | `profile_lazyload_before_single_run_2026-11-13.json`, `profile_lazyload_after_single_run_2026-11-13.json`, `profile_lazyload_six_run_stages_2026-11-14.csv`, `profile_lazyload_six_run_records_2026-11-14.json` | 저장소 밖 OSC 로컬 측정 스크립트 | 프로필 지연 로딩 전후의 단회 시간 및 3쌍 반복 실행 단계 기록. 해석: [Docker 성능 실측](../docs/research/docker-cold-start-measurements.md) |
| `results/docker_performance/` | `kicad_uv_sequential_vs_parallel_stages_2026-11-14.csv`, `kicad_uv_sequential_vs_parallel_outcomes_2026-11-14.csv`, `kicad_uv_sequential_vs_parallel_run_records_2026-11-14.json` | 저장소 밖 OSC 로컬 측정 스크립트 | KiCad·Python 순차/병렬 설치의 단계 시간, 응답·PNG 결과, 6회차 원본 객체. 이미지·Compose 로그 미포함 |
| `results/docker_performance/` | `kicad_in_api_vs_renderer_split_rounds_2026-11-14.csv`, `kicad_in_api_vs_renderer_split_medians_2026-11-14.csv`, `kicad_in_api_vs_renderer_split_run_records_2026-11-14.json` | 저장소 밖 OSC 로컬 측정 스크립트 | KiCad 내장 API와 분리 렌더러의 이미지 크기·첫 응답·첫 PNG 비교, 6회차 원본 객체. 이미지·Compose 로그 미포함 |
| `results/smoke/` | `smoke_*.json` 15개, `injection_http_*.json` 7개 | `smoke/http_smoke.py`, `smoke/injection_http.py` | HTTP 점검 단계 기록. 아래 표 |

### `results/smoke/` 파일

파일 이름은 `smoke_<호스트>_<KST 날짜>_<시각>.json` 또는 `injection_http_<호스트>_<KST 날짜>_<시각>.json`이다. 호스트 표기: `localhost-18000` = 로컬 compose(포트 18000), `sojafit-api-559369539072.asia-northeast3.run.app` = 배포 기본 주소(아래 `PROD`), `newdb---sojafit-api-q5lzmlc4wq-du.a.run.app` = 새 DB 전환 점검용 태그 주소([작업 기록](../docs/worklog/jeongun.md)의 11-11 새 DB 전환). 각 파일의 `commit`·`started_at`·`mode`는 파일 안의 값이다.

| 파일 | 스크립트 | 대상 | `mode` | `commit` | 시작 시각(KST) |
|---|---|---|---|---|---|
| `smoke_localhost-18000_2026-11-10_053242.json` | `http_smoke.py` | 로컬 compose | demo | b8576f8 | 11-10 05:32:42 |
| `smoke_localhost-18000_2026-11-10_054705.json` | `http_smoke.py` | 로컬 compose | demo | d0bd7dd | 11-10 05:47:05 |
| `smoke_localhost-18000_2026-11-10_055128.json` | `http_smoke.py` | 로컬 compose | demo | 5631309 | 11-10 05:51:28 |
| `smoke_localhost-18000_2026-11-10_055423.json` | `http_smoke.py` | 로컬 compose | demo | 5631309 | 11-10 05:54:23 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_225316.json` | `http_smoke.py` | PROD | accounts | 6c38775 | 11-10 22:53:16 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_230015.json` | `http_smoke.py` | PROD | accounts | 3a5985e | 11-10 23:00:15 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_230534.json` | `http_smoke.py` | PROD | accounts | 3a5985e | 11-10 23:05:34 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_232639.json` | `http_smoke.py` | PROD | accounts | e41767a | 11-10 23:26:39 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_232814.json` | `http_smoke.py` | PROD | accounts | 41be150 | 11-10 23:28:14 |
| `smoke_newdb---sojafit-api-q5lzmlc4wq-du.a.run.app_2026-11-11_041537.json` | `http_smoke.py` | 새 DB 점검 주소 | accounts | 27a410d | 11-11 04:15:37 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042105.json` | `http_smoke.py` | PROD | accounts | 27a410d | 11-11 04:21:05 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042119.json` | `http_smoke.py` | PROD | accounts | 27a410d | 11-11 04:21:19 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042439.json` | `http_smoke.py` | PROD | accounts | 27a410d | 11-11 04:24:39 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-13_115305.json` | `http_smoke.py` | PROD | accounts | 2f8298e | 11-13 11:53:05 |
| `smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-13_120624.json` | `http_smoke.py` | PROD | accounts | 2f8298e | 11-13 12:06:24 |
| `injection_http_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_225320.json` | `injection_http.py` | PROD | | 9634c5c | 11-11 22:53:20 |
| `injection_http_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_230021.json` | `injection_http.py` | PROD | | 9634c5c | 11-11 23:00:21 |
| `injection_http_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_230532.json` | `injection_http.py` | PROD | | 9634c5c | 11-11 23:05:32 |
| `injection_http_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_230956.json` | `injection_http.py` | PROD | | 9634c5c | 11-11 23:09:56 |
| `injection_http_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_232913.json` | `injection_http.py` | PROD | | 9634c5c | 11-11 23:29:13 |
| `injection_http_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_233725.json` | `injection_http.py` | PROD | | f554f3c | 11-11 23:37:25 |
| `injection_http_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-12_012039.json` | `injection_http.py` | PROD | | 11dc216 | 11-12 01:20:39 |

단계별 통과·실패와 인젝션 짝 판정은 각 파일 안에 있고 이 표에 옮기지 않는다. 인젝션 짝 판정의 해석: [injection-results.md](../docs/research/injection-results.md).
