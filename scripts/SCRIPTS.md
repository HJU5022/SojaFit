# scripts

## 역할
- 이 폴더: 서비스 코드 밖에서 손으로 돌리는 일회성 측정·점검 스크립트와 그 원시 결과를 둡니다. 저장소 루트에서 실행합니다.
- 넣는 것: 평가셋 평가가 아닌 실측·점검 스크립트, 그 원시 결과(`results/`, 파일 이름은 `<무엇>_<YYYY-MM-DD>.json`).
- 넣지 않는 것: 서비스 코드(`backend/`), 평가셋 실행·동결 스크립트와 평가 결과(`evals/`, `evals/results/`), 측정 해석(`docs/`), 테스트(`tests/`).
- 담당: 각 모듈 담당

## 파일
- `SCRIPTS.md` — 이 문서
- `auth_boundary_after_merge.py` — 로그인 잠금·세션 만료 경계 시각 실측. 격리된 테스트 DB(`TEST_AUTH_DATABASE_URL`, `127.0.0.1:55434/ci_auth`) 전용. `TEST_AUTH_DATABASE_URL=... uv run python scripts/auth_boundary_after_merge.py` → `results/auth_boundary_<KST 날짜>.json`. 해석은 [auth-login-verification.md](../docs/research/auth-login-verification.md)
- `measure_scrypt_concurrent.py` — 동시 scrypt 상한과 프로세스 메모리 실측. **Windows 전용**(`ctypes.windll` 사용, 다른 OS는 import 단계에서 실패)이고 격리된 테스트 DB 전용. `uv run python scripts/measure_scrypt_concurrent.py` → `results/scrypt_concurrent_<KST 날짜>.json`
- `langfuse_skill_check.py` — Langfuse 프롬프트·Skill 연결을 합성 요청 4건으로 점검. `DEMO_MODE=0 uv run python -m scripts.langfuse_skill_check <새 결과 JSON>`. 결과는 `results/`가 아니라 사용자가 준 경로에 쓰며(이미 있으면 실패), 저장소에 둘 때는 `results/`로 옮김. 기본은 기존 development 버전을 조회·대조한 뒤 노드·generation·버전·모델을 확인하고, 로컬/원격 불일치 시 모델 호출 전에 중단. 원격 등록은 `--publish`를 명시해야 하며 `--resume-from`과 함께 쓸 수 없음. 실제 코퍼스 검색·전체 평가·서비스 그래프 통합 검증은 아님
- `results/` — 측정 원시 결과(폴더 설명 파일 없음). 평가 지표는 `evals/results/`
  - `auth_boundary_2026-11-02.json` — 로그인 잠금·세션 만료 경계 실측(`auth_boundary_after_merge.py`)
  - `scrypt_concurrent_2026-11-02.json` — 동시 scrypt·프로세스 메모리 실측(`measure_scrypt_concurrent.py`)
  - `storage_contract_2026-11-02.json` — 합성 벡터 64행·1536차원으로 vector→halfvec 형식·용량·검색 계약 확인(`backend/rag/storage.py` CLI 계열, 실제 코퍼스 결과 아님)
  - `hnsw_exp_base`·`hnsw_exp_A_english`·`hnsw_exp_B_partfilter`·`hnsw_exp_C_kure`·`hnsw_exp_D_qwen` `_2026-11-01.json` — 검색 색인(정확 검색 대 HNSW) 비교 실험 5건, 19문항 Recall@5·MRR·지연. 측정 스크립트는 저장소 밖(`전자_데이터시트/evidence/hnsw_exp/`)
  - `parser_accuracy_2026-11-01.json`·`parser_truth_2026-11-01.json`·`parser_speed_2026-11-01.jsonl` — PDF 파서 비교(도구별 행 적중, 정답표, 속도). 스크립트는 저장소 밖
  - `parse_gpu_log_2026-11-01.jsonl`·`parse_gpu_recall_2026-11-01.json`·`parse_gpu_witness_unmatched_2026-11-01.json` — 1,360건 GPU 파싱 로그, 표 숫자 재현율(0.9989), 대조 못 한 값 목록. 스크립트는 저장소 밖
