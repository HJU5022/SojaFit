# scripts

## 역할
- 이 폴더: 서비스 코드 밖에서 손으로 돌리는 일회성 측정·점검 스크립트와 그 원시 결과를 둡니다. 저장소 루트에서 실행합니다.
- 넣는 것: 평가셋 평가가 아닌 실측·점검 스크립트, 그 원시 결과(`results/`, 파일 이름은 `<무엇>_<YYYY-MM-DD>.json`)를 종류별 하위 폴더에 둡니다. 이 폴더 바로 아래에는 파일을 두지 않습니다.
- 넣지 않는 것: 서비스 코드(`backend/`), 평가셋 실행·동결 스크립트와 평가 결과(`evals/`, `evals/results/`), 측정 해석(`docs/`), 테스트(`tests/`).
- 담당: 각 모듈 담당

## 파일
- `SCRIPTS.md` — 이 문서
- `auth/` — 인증 실측 스크립트(잠금·만료 경계, scrypt 동시성). [AUTH.md](auth/AUTH.md)
- `bit_search/` — 비트 후보 + 정확 재정렬 검색 속도·recall 실험 스크립트. [BIT_SEARCH.md](bit_search/BIT_SEARCH.md)
- `hf_jobs/` — Hugging Face Jobs로 GPU 임베딩을 돌리는 스크립트. [HF_JOBS.md](hf_jobs/HF_JOBS.md)
- `db/` — 운영 DB 손 작업(voyage-4-large 적용 점검·마이그레이션·검증). [DB.md](db/DB.md)
- `langfuse/` — Langfuse 프롬프트·Skill 연결 점검 스크립트. [LANGFUSE.md](langfuse/LANGFUSE.md)
- `demo/` — 키 없는 데모가 재생할 LLM 응답을 실제 키로 한 번 기록하고 키 없이 재생해 대조하는 스크립트. [DEMO.md](demo/DEMO.md)
- `smoke/` — 로컬 compose · 배포 주소의 정상 사용자 흐름(로그인 → 판정 · 재개 → 승인 · 견적 → 다른 계정 404)을 HTTP로 한 번 돌려 보는 점검 스크립트. [SMOKE.md](smoke/SMOKE.md) 같은 폴더의 `injection_http.py`는 인젝션 T4 · T6 · T7을 배포 HTTP로 정상/공격 짝으로 보낸다.
- `results/` — 측정 원시 결과(폴더 설명 파일 없음). 평가 지표는 `evals/results/`
  - `auth/` — 인증 실측 결과
    - `auth_boundary_2026-11-02.json` — 로그인 잠금·세션 만료 경계 실측(`scripts/auth/auth_boundary_after_merge.py`)
    - `scrypt_concurrent_2026-11-02.json` — 동시 scrypt·프로세스 메모리 실측(`scripts/auth/measure_scrypt_concurrent.py`)
  - `storage/` — 저장 형식 확인
    - `storage_contract_2026-11-02.json` — 합성 벡터 64행·1536차원으로 vector→halfvec 형식·용량·검색 계약 확인(`backend/rag/storage.py` CLI 계열, 실제 코퍼스 결과 아님)
  - `hnsw/` — 검색 색인(정확 검색 대 HNSW) 비교
    - `hnsw_exp_base`·`hnsw_exp_A_english`·`hnsw_exp_B_partfilter`·`hnsw_exp_C_kure`·`hnsw_exp_D_qwen` `_2026-11-01.json` — 실험 5건, 19문항 Recall@5·MRR·지연. 측정 스크립트는 저장소 밖(`전자_데이터시트/evidence/hnsw_exp/`)
  - `parser/` — PDF 파서 비교와 GPU 파싱
    - `parser_accuracy_2026-11-01.json`·`parser_truth_2026-11-01.json`·`parser_speed_2026-11-01.jsonl` — 도구별 행 적중, 정답표, 속도. 스크립트는 저장소 밖
    - `parse_gpu_log_2026-11-01.jsonl`·`parse_gpu_recall_2026-11-01.json`·`parse_gpu_witness_unmatched_2026-11-01.json` — 1,360건 GPU 파싱 로그, 표 숫자 재현율(0.9989), 대조 못 한 값 목록. 스크립트는 저장소 밖
  - `bit_search/` — 비트 후보 + 정확 재정렬 검색(운영 Supabase, 3-small 1536 시절)
    - `bit_search_2026-11-03.json`·`bit_search_final_2026-11-03.json`·`bit_search_warm_2026-11-03.json` — 50문항 후보 수 N별 시간·recall@50, v1 관련 19문항 최종 점수 확인, 비트 검색만 이어서 잰 시간. 스크립트는 `scripts/bit_search/`. 해석은 [bit-search-measurement-2026-11-03.md](../docs/research/bit-search-measurement-2026-11-03.md)
