# 오세창 작업 기록

> **문서 전용 반영 범위**: 아래 2026-11-02 항목은 `OSC` 로컬에서 수행했던 탐색·구현·검증의 역사 기록이다. 이번 변경에는 임베딩 후보 관련 문서만 포함하며, 여기에 언급된 평가기 코드, 테스트, 입력 표본, 원시 JSON과 모델 캐시는 포함하지 않는다. 따라서 테스트 통과·재현 성공 문구는 현재 `main`의 상태를 증명하지 않으며, 현재 저장소에서는 문서 정합성만 검증한다.

## 2026-11-02 Voyage 후보 변경 독립 감사 후속

- PR #27 피드백 반영: 2026-11-02 확장 평가기·표본·원시 JSON이 저장소에 없으므로 해당 Recall@5·MRR·지연 상세값과 실행 불가능한 실제 PDF·Voyage 재현 명령을 제출용 `EVAL_REPORT.md`에서 제거하고, 로컬 탐색 이력은 `docs/embedding-candidate-investigation.md`에만 남겼다.
- 후보 정합성: 실제 PDF smoke 성공 기록은 Voyage 4 Nano를 포함한 5종으로 맞췄다. 캐시·원시 결과는 저장소 밖이므로 준비 상태를 `통과`가 아닌 `로컬 기록(저장소 밖)`으로 낮추고, 현재 main의 평가기는 확장 자산이 빠진 `일부 통과`로 표시했다.
- 범위: PR #26은 `main`에 병합됐지만, 리뷰어가 번호·판정 상태·용량·사후 등록·ADR 표현을 후속 PR에서 정리한다고 명시했다. 이 변경에서는 그 항목을 선점하지 않고 원시 근거가 없는 임베딩 상세값만 제출 보고서에서 내렸다.
- 재현성: 평가기가 모든 성공·오류·키 없음 결과에 Python과 `numpy`·`sentence-transformers`·`torch`·`transformers`·`openai` 버전을 기록하도록 바꿨다. 기존 Voyage 원시 결과 4건은 당시 버전을 사후 추정하지 않고 미기록으로 표시했다.
- API 정책: OpenRouter Terms 외에 공식 Privacy Policy·ZDR·provider 데이터 정책 출처를 라이선스 문서에 추가했다. Voyage 4는 정책 차단 상태이며 성공 호출·1,024차원 응답 검증 전 최종 모델로 선정하지 않는다. 계정 정책은 변경하지 않았다.
- 클라이언트 캐시: 지원하는 두 모델 키를 번갈아 호출해도 각 SDK 클라이언트를 한 번만 만들도록 캐시 크기를 2로 맞췄다.
- PR 규모 계획: 이번 변경은 Voyage 후보 2종의 계약·평가기·테스트·원시 결과·보고서를 함께 맞추는 단일 목적이지만 핵심 변경이 400줄을 넘는다. 계약과 결과를 분리하면 같은 PR 안에서 검증 근거가 끊기므로 PR은 나누지 않고, PR 본문에 규모·초과 이유·분리하지 않은 이유를 적는다. 커밋은 `평가기와 테스트` → `계약과 정책 문서` → `원시 결과와 보고서`의 논리 단위로 나눈다.
- 검증: 버전 메타데이터와 두 모델 캐시 테스트는 각각 실패하는 RED를 확인한 뒤 최소 구현으로 통과시켰다. 관련 테스트 41건과 전체 테스트 69건이 통과했고 2건은 기존 조건대로 skip됐다. Voyage JSON 4건 파싱, 변경 Markdown 로컬 링크, 비밀정보 모양 값, `git diff --check`도 확인했다.
- 보고서 연결 보완: `EVAL_REPORT.md`에 13종의 증거 수준별 요약을 추가하고, 후보별 선정·중단 이유의 정본인 `docs/embedding-candidate-investigation.md`와 라이선스 정본을 직접 연결했다. 보고서에는 결과·해석을, 상세 문서에는 모델별 조사 근거를 유지한다.
- 연관 문서 정합성 보완: 초기 4종 기준선 작업서의 후속 계획을 역사 기록으로 표시하고 현재 본평가 문서로 연결했다. `evals/EVALS.md`에는 API 정책 차단과 13종 상세 기록 링크를 추가했으며, 후보 평가기 작업서의 확장 전 상황을 과거형으로 고쳤다. `tests/TESTS.md`에는 Voyage 입력 계약·정책 오류·실행환경 메타데이터·두 모델 캐시 검증을 반영했다.

## 2026-11-02 Voyage 후보 계약과 서비스 경계 보완

- 한 일: Voyage 두 후보 추가가 기존 9+2 후보 작업서와 충돌하지 않도록 전용 5절 계약을 만들고, 후보 registry를 실행 11종·조사 2종으로 정렬했다. 현재 서비스 기본값은 `text-embedding-3-small`·`vector(1536)`이며 Voyage는 평가 후보라는 경계를 `SPEC.md`와 평가 문서에 명시했다.
- 해석 변경: 외부 관리형 API와 팀이 별도 추론 서버에 배포하는 자체 API는 최종 모델 확정 뒤 ADR로 결정한다. 로컬 Recall@5·MRR은 후보 선별 자료로 보존하고, 실제 운영 방식의 동일 동결 표본 결과만 최종 선택에 사용한다. 자체 API라면 모델 이미지·GPU/CPU·메모리 비용도 운영 지표에 포함한다.
- 후보 구분: `text-embedding-3-small`, `voyage-4`, `bge-m3`를 외부 관리형 API 우선 비교 대상으로 적고, Qwen 0.6B는 실행 시 provider 확인 대상으로 뒀다. KURE와 Voyage 4 Nano는 로컬 연구 기준점이면서 자체 추론 API를 택할 경우 운영 후보가 될 수 있다. `voyage-4-lite`는 Nano의 저비용 역할을 비교할 수 있는 미평가 API 후보로만 기록했으며 기존 13종 결과 수에는 넣지 않았다.
- 바꾼 파일: `SPEC.md`, `EVAL_REPORT.md`, `docs/specs/embedding-voyage-candidates.md`, `docs/specs/embedding-candidate-runner.md`, `docs/specs/embedding-candidate-runner-plan.md`, `docs/specs/SPECS.md`, `evals/benchmark_embeddings.py`, `tests/test_benchmark_embeddings.py`, Voyage 결과 JSON 4건, 후보·라이선스 문서와 작업 기록
- 확인 못 한 것: Voyage 4는 현재 계정 ZDR 정책으로 차단돼 있고, 나머지 API 후보도 동결 평가셋에서 아직 같은 조건으로 실행하지 않았다. 모델 제공 여부·가격·provider 정책은 재색인 전에 다시 확인해야 한다.
- 검증: Voyage 입력 메타데이터 테스트가 2건 실패하는 RED를 확인한 뒤 query/document 모드와 자동 prompt 기록을 구현했다. API 정책 오류가 품질 지표를 만들지 않는 테스트를 포함한 관련 테스트 39건, 전체 테스트 67건이 통과했고 2건은 기존 조건대로 skip됐다. 기존 원시 측정값은 바꾸지 않고 고정 입력 메타데이터만 보강했으며 JSON 4건을 다시 파싱했다. 5절 작업서 구조·로컬 Markdown 링크·현재 서비스 기본값·`git diff --check`도 확인했다.

## 2026-11-02 Voyage 4 후보 실행 사전 기록

- 목적: 실제 TSC PDF 3건·156청크·사전 고정 질의 9건에서 로컬 `voyage-4-nano`와 OpenRouter `voyage-4`를 기존 성공 후보와 같은 dense cosine `k=5`로 비교한다. 2차 판정 전 smoke이며 최종 선택에는 사용하지 않는다.
- 고정 조건: 두 모델 모두 1,024차원과 query/document 입력 구분을 사용한다. Nano 모델·코드 revision은 `5fb34e870f49f19e79c94d5e118f5ee730133279`, attention은 `sdpa`다. API 모델 ID는 `voyageai/voyage-4`다.
- 보안 점검: Nano 원격 코드 3,491자를 고정 revision에서 확인했다. 외부 프로세스·네트워크·동적 `eval/exec`·파일 쓰기 패턴은 발견되지 않았으며 이는 완전한 보안 감사를 뜻하지 않는다.
- 예산·중단 조건: Nano 신규 모델·패키지 다운로드 상한 2GiB, API 총비용 상한 `$0.02`, 최대 11요청, 자동 재시도 0회다. OOM·revision 불일치·상한 초과·새 호환성 오류가 나면 해당 후보를 중단한다. 키 값은 읽거나 출력하거나 결과에 저장하지 않는다.
- RED/GREEN: Voyage registry·OpenRouter allowlist·1,024차원·query/document 분리 테스트 8건이 먼저 실패했다. 최소 구현 뒤 관련 테스트 37건이 통과했다. 이 기록과 임베딩 탐색 표 #14·#15를 남길 때는 실제 모델 결과를 아직 보지 않았다.
- 실행 결과: Nano는 Recall@5 0.889, MRR 0.744, 1,000청크 5.29초, 질의 p50/p95 53.9/80.5ms였고 완전 오프라인에서 같은 순위 결과를 재현했다. HF·uv 캐시 합계 증가는 약 0.6GB로 2GiB 상한 안이었다.
- API 차단: 첫 명령은 API 호출 전 `PYTHONPATH` 누락으로 실패해 별도 JSON으로 보존했다. 환경만 교정한 요청은 OpenRouter ZDR/data-policy가 유일 endpoint를 제외해 404로 끝났으며 retry는 0이다. 성공 embedding·usage가 없어 Recall@5·MRR·비용 결과는 없고 계정 정책은 변경하지 않았다.
- 검증: Nano 온라인·오프라인의 Recall@5·MRR·문항별 순위가 모두 일치했다. 전체 테스트는 65건 통과·2건 skip이고 `git diff --check`, 후보 문서 13개 항목, 결과 JSON 상태·usage 부재 검사를 통과했다.

## 2026-11-02 임베딩 후보 11종 개별 조사 기록

- 한 일: 후보 11종을 같은 수준으로 평가했다는 오해를 막기 위해 모델별 선정 이유, 조사·실행 과정, 중단 사유, 현재 증거 수준과 다음 평가 조건을 개별 문서로 정리했다.
- 바꾼 파일: `docs/embedding-candidate-investigation.md`, `docs/model-licenses.md`, `docs/DOCS.md`, `docs/worklog/osc.md`
- 근거 구분: 실제 PDF smoke 완료 4종, 합성 프록시만 완료 1종, 호환성 차단 4종, 조사 전용 2종으로 나눴다. 오류 후보를 품질 0점으로 쓰지 않고 실행되지 않은 후보에는 Recall@5·MRR이 없다고 명시했다.
- 검증: 모델별 2차 제목 11개와 문서 내부 링크를 점검했고, `.venv-windows`의 오프라인 전체 테스트는 60건 통과·2건 skip이었다. `git diff --check`도 통과했다.
- 확인 못 한 것: 2차 판정·동결 평가셋·전체 코퍼스가 없으므로 11종 동일 조건 본평가와 최종 모델 선정은 하지 않았다.
- 다음 할 일: 동결 뒤 우선 5종을 동일 조건으로 평가하고, 호환성 후보는 고정 환경을 해결한 경우에만 추가한다. 약관·연구용 후보는 별도 승인과 결과표로 분리한다.

## 2026-11-02 임베딩 본평가 준비 상태 점검

- 한 일: 2차 판정 전 범위의 마지막 단계로 본평가 시작 조건을 저장소 실물과 Docker 캐시에서 읽기 전용으로 점검했다. 2차 판정·동결·최종 모델 선정은 수행하지 않았다.
- 확인 결과: `data/manifest.jsonl`은 1,360행·청크 수 합계 52,244의 메타데이터를 보유하지만 저장소 PDF는 smoke용 3건뿐이다. `evals/FROZEN.json`, 전체 `chunks.jsonl`, `params.jsonl`, `tsc_datasheet_list.csv`는 없고 `evals/dataset_v1.jsonl`은 2행짜리 형식 예시다. BGE·KURE·Qwen·E5의 평가기에 고정한 정확한 revision snapshot은 `sojafit-hf`에 모두 있다.
- 상태 분류: 고정 revision·오프라인 실행기·지표 기록은 통과, 2차 사람 판정·평가셋 동결·API 기준선 승인은 대기, 전체 1,360건 본문 부재는 차단이다. 이 구분을 `EVAL_REPORT.md`의 본평가 준비 표에 기록했다.
- 검증: Windows 전용 `.venv-windows`에서 `UV_PROJECT_ENVIRONMENT=.venv-windows uv run --offline pytest -q`를 실행해 60건 통과·2건 skip을 확인했고 `git diff --check`도 통과했다.
- 확인 못 한 것: 2차 판정 결과, 동결 gold의 실제 건수·해시, 전체 코퍼스 본문 위치, 동결 평가셋에서의 Recall@5·MRR, CPU 배포 지연은 아직 확인할 수 없다.
- 다음 할 일: 담당자가 2차 판정과 차이 합의를 마치고 전체 본문·동결 파일을 제공하면, 비용 상한을 다시 승인받아 동일 입력·동일 검색 조건에서 API 기준선과 로컬 후보를 실행한다. 최종 확정 뒤에만 별도 확인을 받아 탈락 후보 가중치와 평가용 임시 캐시를 삭제한다.

## 2026-11-02 2차 판정 전 임베딩 호환성 재검증 사전 기록

- 목적: 품질 점수 없이 중단된 GTE, Jina v3, Nomic v2 MoE, Arctic v2를 품질 탈락으로 오해하지 않도록 고정 revision과 공식 사용 조건을 기준으로 호환성 변수 하나씩만 바꿔 재검증한다. 이후 저장소의 실제 PDF 3건 smoke로 연결하되 2차 판정·동결·최종 선택은 하지 않는다.
- 이미 본 오류: GTE는 warmup CUDA `AcceleratorError`, Jina v3는 load의 `custom_st` `ModuleNotFoundError`, Nomic은 `einops` `ImportError`, Arctic은 warmup `AssertionError`다. 공식 고정 revision 자료는 각각 Sentence Transformers 3.0 이상, Jina의 3.1.0 지원, Nomic의 `einops`·`megablocks`, Arctic 설정의 Sentence Transformers 2.7.0·Transformers 4.39.3을 가리킨다.
- 변경 변수: GTE는 attention 구현만 `eager`, Jina는 Sentence Transformers만 3.1.0, Nomic은 공식 runtime extras만 추가, Arctic은 모델 설정의 런타임 버전 조합만 적용한다. 질의·문서·revision·batch·GPU·평가 표본은 고정한다.
- 예산: API 호출·비용 `$0`; 처음 승인한 신규 다운로드 상한은 1 GiB였다. Docling의 Linux Torch/CUDA 의존성이 병렬 다운로드되며 uv 캐시가 5.8GB에서 8.3GB로 늘어 즉시 컨테이너를 중단했고, 사용자가 2026-11-02에 실행 전 5.8GB 대비 총 증가 4 GiB(uv 캐시 9.8GB)까지 추가 승인했다. 기존 모델 가중치 캐시를 사용하며 환경변수 값과 키는 읽거나 출력하지 않는다.
- 실행·중단: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`에서 후보당 변경 후 최대 1회만 실행하며 자동 재시도는 0회다. 동일 오류, 새 오류, GPU OOM, revision 불일치가 발생하면 해당 후보를 중단한다. PDF 파싱 환경은 uv 캐시 9.8GB를 넘으면 중단하고 Hugging Face 모델은 네트워크로 받지 않는다.
- RED/GREEN: `error_metadata` 부재로 2건이 예상대로 실패한 뒤, 오류 형식·메시지 300자·단계·retry 0을 보존하는 최소 구현으로 `tests/test_benchmark_embeddings.py` 26건이 통과했다.
- 호환성 재검증 결과: GTE는 `eager` attention 단일 변경 뒤에도 같은 CUDA device-side assert가 발생해 차단됐다. Jina v3와 Arctic은 요구 버전이 오프라인 uv 캐시에 없어 모델 실행 전에 중단됐다. Nomic은 고정 README가 요구하는 `megablocks`가 커밋이 고정되지 않은 Git 설치여서 알 수 없는 외부 코드를 설치하지 않고 보안상 차단했다. 후보별 추가 재시도는 없었다.
- 비용·용량 결과: API 호출과 비용은 0이다. Hugging Face 볼륨은 실행 전후 모두 10.3GB였고 신규 모델 가중치 다운로드는 없었다. 호환성 패키지도 네트워크로 자동 다운로드하지 않았다.
- 실제 PDF smoke 사전 고정: PDF 본문이나 정답 청크를 보기 전에 `1N4148`, `1N5817`, `BZT52C2V4`에 품번·전기 정격·시험 조건 질문을 3건씩 작성했다. 총 9건이며 gold와 정답 숫자는 아직 넣지 않았다. 실제 3문서 청크 전체에서 dense cosine `k=5`로 Recall@5·MRR을 재는 조건을 임베딩 탐색 표 #13에 기록했다.
- PDF 파싱 추가 승인: Linux Torch/CUDA 패키지의 병렬 다운로드가 중단 중에도 진행돼 uv 캐시가 11.6GB까지 증가했고 사용자가 이 상태를 승인했다. 이후 네트워크 차단 상태에서 압축 해제 archive의 Docling·Torch·pdfplumber import는 성공했으나 Docling 분석 모델이 없어 PDF 3건 모두 파싱 전에 실패했다. 공식 API로 layout `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` 171,764,371바이트와 table `fc0f2d45e2218ea24bce5045f58a389aed16dc23` 358,236,323바이트를 확인했고 사용자가 두 고정 snapshot에 한해 추가 1GB 상한을 승인했다.
- 실제 PDF 파싱·청킹 결과: 고정 layout/table snapshot과 고정 MiniLM tokenizer `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`를 로컬 경로로 전달했다. 모델 파일 사용량은 505.5MiB, tokenizer는 698,829바이트였다. PDF 3건은 각각 5/6/7쪽, 표 5/6/7개로 파싱됐고 표 숫자 witness는 81/81, 49/49, 385/385가 일치했다. 기존 card chunker는 서로 다른 청크 156개를 만들었다.
- 수동 gold: 모델 결과를 보기 전에 1N4148의 VRRM·VF 조건·trr 조건, 1N5817의 VRRM·VF 조건·IFSM 조건, BZT52C2V4의 VZ/IZT·동적 저항·패키지/전력 청크를 PDF·쪽·표 행으로 대조했다. 전체 156청크와 9질의를 `embedding_real_pdf_smoke_v0.jsonl`에 결합했으며 마지막 질문만 두 gold 청크를 가진다.
- 실제 PDF 로컬 탐색 기록: KURE·BGE·Qwen·E5의 Recall@5·MRR·지연을 기록했지만 평가기와 원시 JSON은 저장소에 반영하지 않았다. 특히 Qwen의 `10.37초`는 기존 Windows 30청크 원시값 `10.372056...초`와 같고 실제 PDF 원시 JSON이 없어 재측정값인지 확인할 수 없다. 따라서 이 상세값은 제출용 `EVAL_REPORT.md`와 모델 선정 근거에서 제외했다. 호환성 차단 4종도 저장소에서 재현할 수 있는 결과로 취급하지 않는다.
- 해석: 3문서·9질의 dense-only smoke에서는 KURE가 가장 높은 MRR이었다. 그러나 네 성공 모델 모두 패키지와 전력 두 근거가 필요한 BZT52C2V4 질문을 top-5에서 놓쳤고, 표본이 작고 품번이 직접 포함돼 최종 선택에는 사용할 수 없다. 2차 판정·동결·전체 코퍼스 본평가 전까지 모든 결과는 최종 결정 부적격이다.

## 2026-11-02 임베딩 확장 후보 프록시 실행 기록

- 목적: 기존 30청크·18질의 프록시와 동일한 dense 검색 조건에서 Qwen 재측정과 GTE, multilingual-E5, Jina v3, Nomic v2, Arctic v2의 Recall@5·MRR·1,000청크 시간·22,000벡터 질의 지연을 측정한다. 동결 전 smoke test이므로 최종 모델 확정 근거로 승격하지 않는다.
- 예산: 신규 핵심 가중치 예상 합계 약 6.8GiB, 캐시·메타데이터 포함 신규 다운로드 상한 9GiB. API는 호출하지 않으며 비용 상한은 $0이다.
- 환경: RTX 5060 Laptop GPU 8GB, Docker `sojafit-hf`·`sojafit-uv` 캐시를 사용한다. BGE-M3와 KURE-v1은 Docker 캐시에 있으며 기존 결과를 재사용한다.
- 원격 코드 점검: GTE, Jina v3, Nomic이 외부 코드 저장소를 참조함을 실행 전에 발견했다. 외부 코드 SHA를 각각 고정하고 `code_revision` 전달·결과 기록 테스트를 추가했다. Arctic는 모델 저장소 내부 코드를 모델 SHA와 같은 값으로 고정했다.
- 실행 명령: `docker run --rm --gpus all -v "${PWD}:/workspace" -v sojafit-hf:/root/.cache/huggingface -v sojafit-uv:/root/.cache/uv -w /workspace ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv run --isolated --with sentence-transformers --with torch python evals/benchmark_embeddings.py --model MODEL --output evals/results/embedding_MODEL_2026-11-02.json`
- 중단 조건: 모델별 OOM·실행 오류·15분 이상 무출력 또는 누적 신규 캐시 9GiB 초과 시 해당 모델을 중단한다. 자동 재시도하지 않고 오류와 단계를 기록한다.
- 실행 결과(로컬 탐색·원시 미반영): Qwen `3.63초`, multilingual-E5의 품질·지연, GTE·Jina·Nomic·Arctic의 오류를 로컬에서 기록했지만 대응 원시 결과와 확장 평가기는 저장소에 반영하지 않았다. Qwen `3.63초`는 검수 가능한 원시가 없으므로 사용하지 않고, 저장소 원시 JSON이 있는 30청크 오프라인 값 `3.83초`만 재현 가능한 기록으로 유지한다. API는 호출하지 않았다.
- 저장·용량 결과: 온라인·오프라인 원시 JSON과 실패 JSON을 `evals/results/embedding_*_2026-11-02.json`에 저장했다. `sojafit-hf` 볼륨은 6.4GB에서 10.3GB로 약 3.9GB 늘어 9GiB 상한 안이었다. 전용 모델 Docker 이미지는 만들지 않고 공통 이미지·uv 캐시와 분리된 모델 볼륨을 사용했다.
- 해석: 성공 5종의 프록시 MRR은 API 0.907, KURE 0.894, Qwen 0.875, BGE 0.863, E5 0.785 순이다. 실패 4종은 품질 탈락이 아니라 현재 고정 환경에서 비교 불가로 둔다. 18질의 프록시 결과를 최종 모델 확정에 사용하지 않는다.
- 후속 정리: 2차 판정까지 끝내고 최종 임베딩 모델을 확정한 뒤 탈락 모델의 정확한 캐시 경로와 회수 용량을 제시해 별도 확인을 받고 로컬 가중치를 삭제한다. 평가 결과와 revision·라이선스 기록은 보존한다.

## 2026-11-02 임베딩 후보 확장 평가기 설계 및 구현

- 한 일: 팀장이 지시한 미평가·연구용 임베딩 후보 비교를 준비하기 위해 실행 후보 9종과 조사 전용 후보 2종을 확정했다. 모델별 query/document 입력 형식, 불변 revision, 라이선스·운영 분류, 키 없는 API 처리, 오프라인 로더와 오류 메타데이터를 평가기에 구현했다. Jina v3는 연구용 실행으로, EmbeddingGemma와 Jina v4는 조사 전용으로 분리했다. 최종 모델 확정은 2차 판정과 평가셋·코퍼스 표본 동결 이후로 유지했다.
- 바꾼 파일: `evals/benchmark_embeddings.py`, `tests/test_benchmark_embeddings.py`, `tests/TESTS.md`, `docs/model-licenses.md`, `docs/DOCS.md`, `docs/specs/embedding-candidate-runner.md`, `docs/specs/embedding-candidate-runner-plan.md`, `docs/specs/embedding-model-baseline.md`, `docs/specs/SPECS.md`, `docs/worklog/osc.md`
- 실행한 명령과 결과: catalog 부재 RED 4건, 입력 어댑터 부재 RED 11건, 실행 메타데이터 부재 RED 5건, 라이선스 문서 부재 RED 1건을 확인했다. GREEN에서 후보 테스트 15건과 중앙 API 경계 포함 21건이 통과했고, 최종 전체 가벼운 테스트는 46건 통과·2건 skip이었다. 공식 모델 카드와 라이선스를 2026-11-02에 다시 확인해 8개 로컬 실행 후보와 조사 후보 2개의 40자리 revision을 고정했다. 모델 다운로드와 API 호출은 하지 않았다.
- 확인 못 한 것: 신규 후보의 실제 모델 로드·다운로드 크기·VRAM, `HF_HUB_OFFLINE=1` 재실행, 프록시 Recall@5·MRR·지연, 동결 평가셋과 실제 코퍼스 표본 결과는 아직 측정하지 않았다.
- 다음 할 일: 2차 판정과 50건 평가셋·코퍼스 표본 동결 뒤 사전등록 조건을 확정하고, 비용·다운로드·중단 조건을 먼저 승인받아 실행 후보를 같은 환경에서 비교한다.

## 2026-10-30 임베딩 평가 리뷰 반영

- 한 일: 예비 기본 선택인 `text-embedding-3-small`과 본평가 기준선을 일치시켰다. `BM25 + text-embedding-3-small`을 기준선으로 두고 KURE와 Qwen 후보 구성을 각각 한 번에 하나만 바꾸도록 사전등록·평가 리포트·작업서를 정렬했다. 검색 품질 지표와 실행 환경이 다른 운영 프로파일을 분리하고, 로컬 지연이 RTX 5060 Laptop GPU 측정값이며 2026-10-30 배포 기준 Cloud Run CPU 1 vCPU·메모리 512 MiB를 대표하지 않는다는 점을 각 로컬 행에 연결했다. 로컬 모델 배포 시 메모리 증설·CPU 재측정이 필요하다는 점도 추가했다.
- 바꾼 파일: `evals/PREREGISTER.md`, `EVAL_REPORT.md`, `docs/specs/embedding-model-baseline.md`, `docs/worklog/osc.md`
- 실행한 명령과 결과: 머지된 `origin/main`을 `OSC`에 fast-forward하고 기준선 관련 문구를 `rg`로 대조했다. Docker의 `uv sync --frozen --dev --offline` 뒤 전체 테스트를 실행해 3건이 통과했다.
- 확인 못 한 것: Cloud Run CPU 환경의 실제 임베딩 지연, 로컬 모델별 최소 메모리, 100문서 실제 청크의 본평가 결과는 아직 측정하지 않았다.
- 다음 할 일: 100문서 실제 청크와 교차 라벨한 질의가 준비되면 API 기준선, KURE, Qwen을 사전등록 조건 그대로 비교한다.

## 2026-10-30 임베딩 모델 예비 기준선

- 한 일: 실제 코퍼스 수집 전에 `text-embedding-3-small`, `bge-m3`, `KURE-v1`, `Qwen3-Embedding-0.6B` 후보를 거르기 위한 30청크·18질의 프록시 표본과 재현 스크립트를 만들었다. 로컬 세 모델의 Recall@5, MRR, 1,000청크 처리 시간, 22,000벡터 exact search 지연을 같은 RTX 5060 Laptop GPU에서 측정하고 `HF_HUB_OFFLINE=1` 재실행을 확인했다. 사용자가 비용을 확인하고 약 2원 한도 실행을 승인한 뒤 OpenRouter의 `openai/text-embedding-3-small`도 같은 표본으로 측정했다. 이 실행은 결과를 보기 전 기대 범위를 적지 못한 탐색적 smoke test라 G5 개선 실험으로 세지 않는다. 원격 최신 main `44dadbf`를 fast-forward로 반영한 뒤, 최신 데모 규칙에 맞춰 미등록 질의의 BM25-only 추출형 fallback과 실제 100문서 후속 평가를 문서화했다.
- 실험 조건과 승인 근거: 목적은 네 후보의 검색 품질·지연·비용·오프라인 적합성을 같은 프록시에서 비교하는 것이다. 청크 30개, 질의 18개, dense cosine, gold 1개, 리랭커 없음, RTX 5060 Laptop GPU를 고정했다. API 예산 상한은 약 2원으로 사용자가 비용 안내 뒤 승인했고, Qwen 추가도 약 1.21GB 다운로드·API 비용 $0 안내 뒤 사용자가 명시적으로 요청했다. 오류·OOM·사용자 중단 시 반복 호출하지 않는 것을 중단 조건으로 뒀고 Qwen query instruction은 실행 전에 영문 한 문장으로 고정했다. 단, 이 조건을 저장소 worklog에 적은 시점은 실행 뒤 규칙 검수 때였으므로 다음 무거운 실험부터는 명령 실행 전에 기록한다.
- 바꾼 파일: `SPEC.md`, `backend/services/llm.py`, `backend/services/SERVICES.md`, `tests/test_llm.py`, `tests/TESTS.md`, `docs/specs/embedding-model-baseline.md`, `docs/specs/SPECS.md`, `evals/embedding_sample_v0.jsonl`, `evals/benchmark_embeddings.py`, `evals/EVALS.md`, `evals/PREREGISTER.md`, `evals/results/embedding_*_2026-10-30.json`, `EVAL_REPORT.md`, `docs/worklog/osc.md`
- 실행한 명령과 결과: 로컬 후보는 Docker의 `uv run --offline --isolated --with sentence-transformers --with torch`로 최종 비교했다. `bge-m3`는 Recall@5 1.000, MRR 0.863, 1,000청크 5.95초였고 `KURE-v1`은 Recall@5 1.000, MRR 0.894, 1,000청크 5.68초였다. Qwen은 Recall@5 1.000, MRR 0.875, 1,000청크 3.83초, 질의 p50/p95 61.8/82.9 ms였으며 캐시 snapshot 경로를 직접 로드해 `HF_HUB_OFFLINE=1`을 통과했다. 최초 Windows 임시 환경 결과는 10.37초, 43.7/49.0 ms였으나 실행 환경이 달라 비교표에서 제외하고 원시 JSON으로만 보존했다. OpenRouter API 결과는 Recall@5 1.000, MRR 0.907, 1,000청크 7.02초, 질의 p50 918.7 ms였다. 전체 API 사용량은 45,699토큰, $0.000914였다. 첫 실행에서 22,000행 생성의 `numpy.tile` 축 오류를 재현해 행 방향 반복으로 수정한 뒤 재실행했다. 저장소 규칙 검수에서 API 직접 호출을 발견해 `backend/services/llm.py`의 단일 임베딩 호출 경계로 옮겼고, `embed_texts` 부재로 실패하는 RED를 확인한 뒤 mock client 계약 테스트를 통과시켰다.
- 확인 못 한 것: 100개 PDF 실제 청크, CPU/Cloud Run 지연, 최종 Dockerfile의 압축 이미지 크기는 아직 측정하지 않았다.
- 다음 할 일: `PREREGISTER.md` #1·#2의 고정 조건대로 100개 PDF 실제 청크와 사람이 교차 라벨한 질의에서 `BM25 + text-embedding-3-small`을 기준으로 KURE와 Qwen 후보 구성을 각각 비교한다. 그 뒤에만 `vector(N)`과 Migration 2를 확정한다.

## 2026-10-30 DB 테이블 정의서 초안 작성

- 한 일: SojaFit의 사용자, 회로, 부품·문서, 분석·판정, 승인 견적 데이터를 위한 테이블 정의서 초안을 작성했다. LangGraph 관리 테이블과 직접 관리하는 업무 테이블을 구분하고, `pgvector`·ERD·Migration은 현재 범위에서 제외했다. 확정되지 않은 항목은 가정·미정 및 추가 검토 항목 A-01~A-20으로 분리했다.
- 바꾼 파일: `db/table-definition.md`, `db/DB.md`, `docs/worklog/osc.md`, `docs/worklog/WORKLOG.md`
- 실행한 명령과 결과: `git branch --show-current`로 `OSC` 브랜치를 확인했다. `git diff --check`와 Markdown 구조·미정 항목 검색으로 문서 형식과 검토 항목을 확인했다.
- 확인 못 한 것: 로그인 방식, 사용자 ID 형식, 회로 파일 저장 방식, 판정·역할·사양 코드, 삭제 정책은 팀 합의 전이라 확정하지 않았다. ERD, Migration SQL, `pgvector` 구조는 작성하지 않았다.
- 다음 할 일: 팀이 정의서와 추가 검토 항목을 검토한 뒤 관계와 코드 정책을 확정하고 ERD를 작성한다.

## 2026-11-04 수퍼바이저 모델 5종 비교 계약 초안

- 한 일: 확정 전 참고 노드 구조를 전제로 수퍼바이저 후보 5종을 동결 v2 70문항에서 각 3회 비교하는 실험 계약을 작성했다. 모델 ID는 `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna`, `deepseek/deepseek-v4.1-flash`, `meta/muse-glimmer-30b`, `cohere/command-a-plus`로 축약 없이 고정했다.
- 비교 방식: 1,050회 주 실행의 deterministic objective scoring, three-run stability, robustness/failure handling, blind pairwise A/B swap, end-to-end, usage·cost·latency를 분리했다. 70문항 전체·10개 후보쌍·두 위치의 pairwise는 별도 1,400 judge decisions로 계산해 별도 예산으로 뒀다.
- 지표: 결과표의 metric 이름은 영어로 유지하고 각 값의 정의·계산식·방향을 적었다. `[Measured]`, `[Calculated]`, `[Estimated]`, `[Human Judgment]`, `[LLM Judge]`, `[Public Specification]`을 구분하며 `hallucination`과 `health`는 표준 철자를 사용한다.
- 안전 경계: ZDR/data collection 조건 미충족은 입력을 보내지 않고 `Not Measured`로 남긴다. 동결 평가셋·임베딩·검색 구성을 바꾸지 않으며, 참고 노드 그림과 최종 모델·judge 모델은 아직 확정하지 않았다.
- 바꾼 파일: `docs/experiments/supervisor-model-comparison.md`, `docs/experiments/EXPERIMENTS.md`, `SOJAFIT.md`, `docs/worklog/osc.md`
- 검증: `uv run --no-sync pytest -q tests/repo/test_repo_layout.py tests/evals/test_frozen_evals.py`에서 8건이 통과했다. 필수 model ID·실행 수식·metric 철자 검사와 `git diff --check`도 통과했다. API 호출과 실측은 수행하지 않았다.

## 2026-11-04 수퍼바이저 후보 비교 실행기 준비

- 한 일: 동결 v2 70건을 후보 5종에서 각 3회 실행하는 1,050-job manifest와 model별 worker를 구현했다. LLM 호출은 `backend/services/llm.py`의 `evaluation_chat()` 한 곳만 통하며 full model ID, JSON schema, usage, ZDR·data collection deny·fallback 금지를 요청에 넣는다.
- 안전·재개: frozen hash·prompt hash·provider policy 불일치 시 중단하고, model별 raw-call·시간·예약비용 상한을 둔다. schema 오류만 case당 2회 재시도하고 SDK retry는 0회다. 각 job 뒤 parsed output을 원자 저장하며 예외 원문, expected, gold_chunks, raw prompt/response는 결과에 저장하지 않는다.
- 집계: label이 있는 관련 35건의 `Question Type Accuracy`, 70건 3회 출력의 `Three-Run Exact Agreement`, token·actual cost·p50/p95 latency를 분리했다. 비관련 35건은 실행 대상이지만 route gold가 없어 `Unscored Case Count=35`로 남긴다.
- 공개 catalog 확인: 5종 모두 2026-11-04 OpenRouter catalog와 `zdr=true` filter에 있다. 보수적 primary 210-call 예약 비용은 model별 `$0.251597`, `$0.251597`, `$0.128003`, `$0.738663`, `$0.754791`, 합계 `$2.124651`이다. 제안 상한 합계 `$2.50`은 아직 승인 전이다.
- 바꾼 파일: `backend/services/llm.py`, `evals/runners/run_supervisor_models.py`, 대응 테스트·폴더 문서, `docs/experiments/supervisor-model-comparison.md`, `SOJAFIT.md`, 이 작업 기록
- 확인: 최종 전체 시험은 284건 통과·26건 skip이다. API 없이 `evals/results/supervisor/2026-11-04-preflight-v3/manifest.json`에 code hash를 포함한 1,050개 고유 job을 만들었다. 이번 작업 중 생성한 code hash 이전 preflight 두 개는 혼동을 막기 위해 제거했다. 승인된 본실행, pairwise judge, robustness, end-to-end, 비관련 35건과 evidence/action의 사람 gold 합의는 아직 수행하지 않았다.
- 검증 중 외부 요청: stale code manifest가 API client 생성 전에 막히는 회귀 시험을 처음 추가할 때 차단 구현 전 worker가 `openai/gpt-6-luna` 210건을 실행했다. 전부 `NotFoundError`, 성공 0건, usage의 actual cost 보고값 합계 `$0.00`, 로컬 보수 예약값 `$0.2515971`이었다. 예외 원문과 응답 본문은 출력하지 않았다. 즉시 code hash fail-closed 검사와 API client 미생성 assertion을 추가했다.
- 비용 보강: local 예약 상한 외에 OpenRouter `provider.max_price`를 공개 catalog 단가로 고정하고 `sort=price`를 적용했다. ZDR endpoint가 더 비싸면 요청이 실패하므로 공개 단가보다 비싼 provider로 우회하지 않는다.

## 2026-11-04 수퍼바이저 비교 실행 전 감사 보완

- 유지한 범위: 동결 v2 70문항은 줄이거나 수정하지 않았다. 그중 `question_type` gold가 없는 35문항도 3회 모두 실행 대상에 둔다. 다만 objective score를 임의 생성하지 않고 `Known Limitation`에 35개 ID와 제외 사유를 기록한다.
- 통계 보완: 세 반복을 독립 210문항으로 세지 않고 run별 accuracy·Macro-F1의 mean/min/max를 낸다. 누락·실패는 stability와 completion 분모에서 제외하지 않으며 전체 70문항·210출력을 분모로 둔다. reason code는 여섯 canonical value로 제한했다.
- 실행 안전 보완: 유료 명령에 `--confirm-live`를 추가하고, 같은 manifest hash에서 provider metadata가 남은 성공 smoke 없이는 full run을 시작하지 않는다. full run은 smoke provider를 `provider.only`로 고정하고 응답 provider가 달라지면 중단한다. 연속 provider 오류 3회에서도 중단한다.
- 재개·비용 보완: 각 job 뒤 `cumulative_raw_calls`와 `cumulative_reserved_usd`를 원자 저장하며 재개 시 전체 cap에서 차감한다. 이전 누적값이 cap에 닿았으면 API client 생성 전에 중단한다.
- 복수 비교 준비: `plan`이 주 실행 1,050 jobs 외에 blind pairwise A/B swap 1,400 decisions와 원문 내부를 보존하고 앞뒤 빈 줄만 추가하는 robustness 70건을 별도 계획으로 만든다. judge model·추가 비용·end-to-end 구조는 아직 확정 또는 승인하지 않았으므로 실행하지 않는다.
- 바꾼 파일: `backend/services/llm.py`, `evals/runners/run_supervisor_models.py`, 대응 테스트·폴더 문서, `docs/experiments/supervisor-model-comparison.md`, `docs/worklog/osc.md`
- 외부 실행: 이 보완에서는 API 호출, 실제 모델 평가, commit, push를 하지 않았다.
- 검증: targeted test 30건과 전체 `pytest` 290건이 통과했고 26건은 기존 조건부 skip이다. `py_compile`과 `git diff --check`도 통과했다. `evals/results/supervisor/2026-11-04-preflight-v5/`의 새 manifest는 5 models·70 cases·3 runs·1,050 unique jobs이고 code hash가 현재 파일과 일치한다. 추가 계획은 pairwise 1,400건, robustness 70건이다.

## 2026-11-04 수퍼바이저 후보 smoke와 본평가 중단

- smoke 결과: `anthropic/claude-haiku-5.5`와 `openai/gpt-6-luna`는 `NotFoundError`, `meta/muse-glimmer-30b`는 세 차례 schema 불일치 뒤 `ValidationError`로 실패했다. 실패 모델은 재시도하거나 다른 endpoint를 찾지 않았다. `deepseek/deepseek-v4.1-flash`는 `Morph`, `cohere/command-a-plus`는 `Cohere` provider에서 smoke를 통과했다.
- 본평가 결과: 먼저 시작한 `deepseek/deepseek-v4.1-flash`에서 24개 output이 완료된 뒤 3개 `ValidationError`가 기록됐다. 사용자 지시에 따라 실행 프로세스 두 개를 중단했고 추가 호출을 멈췄다. 누적 raw call은 37회, 보수 예약 비용은 `$0.02256473`, 완료 응답 24건이 보고한 실제 비용 합계는 `$0.00156553`이다.
- 추가 진행: `cohere/command-a-plus` 본평가, pairwise, robustness, end-to-end는 시작하지 않았다. 결과 요약은 `evals/results/supervisor/2026-11-04-preflight-v5/evaluation_outcome.json`에 남겼다. smoke artifact가 usage를 저장하지 않으므로 smoke actual cost는 `Not Reported`다.

## 2026-11-04 수퍼바이저 평가 중단 기준 정정과 재개

- 정정: 사용자의 “실패하면 추가 진행하지 않음”은 호출 자체가 완전히 실패한 모델에만 적용한다. 이전에는 `deepseek/deepseek-v4.1-flash`의 문항별 schema 실패를 모델 실패로 잘못 해석해 일찍 중단했다.
- 실행기 수정: provider 응답의 schema가 틀려도 actual model·provider·usage를 보존하고 해당 output을 `ValidationError`로 확정한다. 재개 시 이미 세 번 schema 실패한 job은 다시 호출하지 않으며, `RateLimitError`와 `EvaluationLimitError`만 재개 대상으로 남긴다. targeted 31건과 전체 291건이 통과하고 26건은 조건부 skip이었다.
- 실행 결과: 호출 자체가 불가능한 `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna`만 제외했다. `deepseek/deepseek-v4.1-flash`는 126/210 outputs(106 schema 성공·17 schema 실패·3 rate limit)에서 `RateLimitError`가 지속되어 pause했다. `meta/muse-glimmer-30b`는 83/210(3 성공·79 schema 실패·1 budget limit), `cohere/command-a-plus`는 96/210(28 성공·67 schema 실패·1 budget limit)에서 각각 승인된 `$0.85` 예약 상한으로 중단됐다.
- 비용 구분: 보수 예약값은 deepseek `$0.112012215`, meta `$0.8493165000000013`, cohere `$0.8474657999999993`이다. cost가 실제 보고된 usage record만 합친 부분값은 각각 `$0.010941501`, `$0.08743718`, `$0.1100652`이며 smoke 비용과 usage 누락 호출은 포함하지 않는다.
- 후속 실행: 예약 상한을 임의로 올리지 않았고 pairwise·robustness·end-to-end는 실행하지 않았다. 현재 평가 실행 프로세스는 없다.

## 2026-11-04 부분 본 테스트 결과 문서화

- 분류 정정: 모델당 한 건의 호출 가능 여부 확인만 smoke이고, 이후 동결 v2 70문항×3회 manifest로 수행한 요청은 실제 본 테스트다. 210 outputs를 완료하지 못했으므로 상태는 `Partial Measured Main Test`로 기록했다.
- 문서 반영: `docs/experiments/supervisor-model-comparison.md` 결과 절에 모델별 planned·recorded output, schema 성공·실패, raw calls, token, p50·p95 latency, 부분 보고 cost, 예약 cost, 부분 routing summary를 기재했다. 서로 다른 case prefix와 미완료 분모 때문에 최종 순위에는 사용하지 않는다고 명시했다.
- 실행 상태: 확인 시 `run_supervisor_models` smoke·run 프로세스는 0개였으므로 종료할 추가 프로세스는 없었다. `evaluation_outcome.json` 상태를 `partial_main_test_at_safety_limits`로 갱신했다.

## 2026-11-04 Haiku·Luna ZDR routing parameter 수정

- 원인 확인: 인증된 OpenRouter ZDR endpoint 목록에서 `anthropic/claude-haiku-5.5` endpoint는 `temperature`를 지원 parameter로 공개하지 않았고, `openai/gpt-6-luna`의 ZDR Azure endpoint는 `temperature`와 `max_tokens` 대신 `max_completion_tokens`를 사용했다. 기존 공통 payload와 `require_parameters=true`의 조합이 모든 endpoint를 routing 대상에서 제거했다.
- 수정: `evaluation_chat()`이 Haiku에는 `temperature` 없이 `max_tokens`, Luna에는 `temperature` 없이 `max_completion_tokens`, 나머지 후보에는 기존 `temperature=0`·`max_tokens`를 보낸다. ZDR, `data_collection=deny`, `require_parameters=true`, fallback 금지, 가격 상한은 변경하지 않았다.
- 범위: 외부 model smoke나 본 테스트는 실행하지 않았다. 과거 `preflight-v5`는 당시 code hash와 부분 본 테스트 결과를 보존하며, 다음 실행은 새 manifest에서 시작해야 한다.

## 2026-11-04 Haiku·Luna routing 수정 smoke 확인

- 새 실행: 현재 code hash로 `evals/results/supervisor/2026-11-04-routing-fix-smoke-v1/` manifest를 만들고 수정 대상 두 모델만 모델별 `$0.02`, 180초 상한에서 smoke했다.
- 결과: `anthropic/claude-haiku-5.5`는 `Google`, `openai/gpt-6-luna`는 `Azure` provider에서 actual model ID와 schema output을 포함해 성공했다. 이전 `NotFoundError`의 원인이 모델 부재가 아니라 공통 generation parameter와 `require_parameters=true`의 충돌이었다는 가설이 실측으로 확인됐다.
- 범위: 본 테스트는 시작하지 않았고 실행 후 `run_supervisor_models` 프로세스는 0개다. smoke actual cost는 artifact에 usage를 저장하지 않아 `Not Reported`다.

## 2026-11-04 · 수퍼바이저 본 테스트 실행 전 차단 수정(실행 안 함)

- 예산 수정: 호출 전 보수 예약은 유지하되 OpenRouter가 `usage.cost`를 반환하면 해당 호출을 실제 보고 비용으로 정산한다. cost가 없거나 호출 자체가 실패하면 예약값을 유지한다. 과거처럼 실제 보고 비용보다 예약값만으로 먼저 중단되는 편향을 줄였다.
- 호출 증거 수정: 과거 호출 성공을 현재 smoke로 복사하지 않는다. `import-evidence`가 동일 dataset·prompt·provider policy와 exact model/provider를 확인하고, 원본 manifest·artifact hash를 `provider_evidence.json`에 고정한다. 원본이 바뀌면 본 실행 전에 거부한다.
- 준비 결과: API 없이 `evals/results/supervisor/2026-11-04-main-ready-v1/`에 1,050-job manifest를 만들고, 기존 결과 두 폴더에서 5개 모델의 provider evidence를 가져왔다. 본 테스트·추가 smoke·pairwise·robustness·end-to-end 호출은 실행하지 않았다.
- 검증: 새 회귀 테스트는 구현 전 2건 실패를 확인했고 구현 후 통과했다. 관련 로컬 테스트는 38건 통과했다.

## 2026-11-04 · 수퍼바이저 후보 단계 1 실행(70문항 1회)

- 설계 변경: 후보 5종을 각 70문항 1회로 같은 조건에서 비교했다. 실행기에 `--run-index`를 추가했고 지정하지 않은 반복을 호출하지 않는 회귀 테스트를 RED→GREEN으로 확인했다. 관련 로컬 테스트는 39건 통과했다.
- 실행 범위: `evals/results/supervisor/2026-11-04-stage1-v1/`에서 run index 1만 모델별로 순차 실행했다. pairwise, robustness, end-to-end는 실행하지 않았고, 이번 최종 선정에 추가 반복 실행을 요구하지 않는다.
- 완료 결과: `anthropic/claude-haiku-5.5` 70/70(schema valid 48), `openai/gpt-6-luna` 70/70(66), `meta/muse-glimmer-30b` 70/70(1), `cohere/command-a-plus` 70/70(20)을 기록했다. `deepseek/deepseek-v4.1-flash`는 `RateLimitError` 3회 연속으로 3/70에서 provider stop했다.
- 35개 labeled case의 `Question Type Accuracy`: `anthropic/claude-haiku-5.5` 22/35, `openai/gpt-6-luna` 35/35, `meta/muse-glimmer-30b` 1/35, `cohere/command-a-plus` 8/35. DeepSeek은 비교 불가다.
- 비용: raw call 589회, `Budget-Accounted Cost` 합계 `$0.21675608`, cost가 보고된 561회 호출을 합친 `Reported Cost Sum` `$0.19945832`다. 전자는 미보고 호출의 보수 예약값을 포함하고 후자는 포함하지 않으므로 어느 쪽도 단독으로 실제 총 청구액이라 부르지 않는다.
- 기록: 동일 폴더의 manifest·provider evidence·모델별 parsed output·`stage1_summary.json`과 `docs/experiments/supervisor-model-comparison.md`에 상태·오류·점수·비용·latency를 기록했다. 이 1회 실측으로 `openai/gpt-6-luna`를 실험상 최종 선정했으며 추가 반복 실행은 요구하지 않는다. 서비스 기본값 적용은 조장 소유 ADR·`SPEC.md` 갱신 뒤 별도 변경으로 수행한다.

## 2026-11-04 · 수퍼바이저 실측 PR 검수 보완

- 재현 근거: 실행기와 회귀 테스트, stage1 manifest·provider evidence·모델별 parsed output·집계 JSON을 같은 PR에 포함했다. 사용자 입력·raw response·예외 원문·API key는 포함하지 않았다.
- 문서 정합성: 완료 전 상태로 남아 있던 AC-08을 완료 뒤 선정 범위로 고쳤다. Luna는 이 실험의 최종 선정이고, 서비스 정본과 실제 기본 모델 전환은 조장 소유 ADR·`SPEC.md` 갱신 전에는 완료로 표시하지 않는다.
- PR 규칙: 실행 코드·테스트·sanitized 원시 결과·실험 결론을 한 실험의 재현 단위로 묶었다. 핵심 변경이 400줄을 넘는 이유와 분리하지 않은 이유는 PR 본문에 기록한다.
