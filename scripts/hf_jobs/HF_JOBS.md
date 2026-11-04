# hf_jobs

## 역할
- 이 폴더: 맥에서 못 돌리는 큰 임베딩 모델(Qwen3 4B·8B, KURE, bge-m3)을 Hugging Face Jobs의 GPU로 돌리는 스크립트를 둡니다.
- 넣는 것: HF Jobs 작업 스크립트와, 카드·질의를 비공개 데이터셋 저장소로 주고받는 도우미.
- 넣지 않는 것: 검색·채점 실행기(`evals/runners/`), 받은 벡터 파일(약 2.8GB, 저장소 밖), 토큰(`hf auth login`으로 로그인한 값을 그대로 쓰고 코드에 적지 않음).
- 담당: 검색·데이터

## 파일
- `HF_JOBS.md` — 이 문서
- `hf_job.py` — HF Jobs에서 실행. 비공개 데이터셋의 카드(문서 쪽)와 질의(질문 쪽)를 GPU 모델로 임베딩해 같은 저장소 `out/<키>/`에 올림. `hf jobs uv run --flavor t4-small --timeout 45m --secrets HF_TOKEN scripts/hf_jobs/hf_job.py <저장소> <모델 키> ...`
- `hf_data.py` — 맥에서 실행. `pack`(카드·질의를 비공개 저장소로 올림, TSC 약관상 공개이면 멈춤), `fetch`(결과 벡터를 받아 행 수·노름·NaN 검증 뒤 `vectors/`·`inputs/qvec_<키>.npz`로 바꿈), `delete`(검증 뒤 저장소 삭제). 작업 폴더는 `LAYERS_WORK`(기본 `../전자_데이터시트/evidence/full_grid`)

## 주의
- 데이터시트(TSC)는 재배포가 금지라 `hf_data.py pack`이 비공개 저장소가 아니면 멈추고, 검증 뒤 저장소를 지웁니다(11-03에 두 저장소 모두 지움).
