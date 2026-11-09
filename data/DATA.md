# data

## 역할
- 이 폴더: 서비스·평가가 읽는 고정 데이터를 둡니다. 코퍼스 문서 목록(`manifest.jsonl`), 코퍼스 원본 표본, 평가·시연용 공개 회로, 키 없는 데모의 합성 시나리오와 데모 코퍼스 스냅샷(`demo/`)이 있습니다. Dockerfile이 이 폴더를 이미지에 복사합니다.
- 넣는 것: `manifest.jsonl`(문서 단위 목록), 데이터시트 원본 표본(`corpus/tsc/` 3건), 공개 KiCad 회로(`circuits/`), 키 없는 데모 자료(`demo/`: 합성 시나리오, compose가 로컬 DB에 넣는 코퍼스 스냅샷 42문서 `demo/snapshot/`).
- 넣지 않는 것: 데이터시트 PDF 전체 1,360건·파싱 결과(`docling` 산출물)·전체 청크(`chunks.jsonl`, 데모 스냅샷 `demo/snapshot/` 42문서만 예외)·임베딩 캐시(저장소 밖 작업 자료), 데이터를 만드는 코드(`backend/rag/`), 평가셋(`evals/`), 단위 테스트용 가공 회로(`tests/` 아래), 실제 API 응답 원본.
- 담당: 검색·데이터 (`circuits/`는 평가·문서, `demo/`는 서비스·운영)

전체 PDF·파싱·청크·임베딩 산출물은 저장소에 포함하지 않습니다. 작업자가 지정한 저장소 밖 경로에 둘 수 있지만 이 문서는 특정 로컬 경로의 존재나 전체 처리 완료를 보장하지 않습니다. 저장소에서 확인 가능한 정본은 `manifest.jsonl`과 PDF 표본 3건입니다.

## 파일
- `manifest.jsonl` — 2026-11-01 v1 청킹 당시 체크인한 코퍼스 문서 목록 1,360줄(문서 단위: id, 판본, 출처, sha256, 쪽 수, 청크 수). 현재 `backend/rag/pipeline/chunk.py`도 같은 형식의 새 manifest를 만들고 `backend/rag/pipeline/ingest.py`·`collect.py`가 읽지만, v4h 실행 결과는 저장소 밖 산출물이며 이 파일을 자동으로 갱신하지 않습니다. 원래 PDF 파일 이름은 `source_url` 끝에 있습니다
- `corpus/` — 코퍼스 원본 문서 표본(TSC PDF 3건). [CORPUS.md](corpus/CORPUS.md)
- `circuits/` — 평가·시연용 공개 KiCad 회로와 라이선스. [CIRCUITS.md](circuits/CIRCUITS.md)
- `demo/` — 키 없는 데모의 합성 시나리오(`scenarios.json`)와 compose가 로컬 DB에 넣는 코퍼스 스냅샷(`snapshot/`, TSC 42문서 · 청크 1,556개, 임베딩 없음). [DEMO.md](demo/DEMO.md)

## 기준

G3: **서로 다른 청크 1만 개 이상, 서로 다른 문서 50건 이상**(복제와 변형 제외), 문서 파싱 1종 이상. 정본은 [docs/GATES.md](../docs/GATES.md)입니다.

수집일은 `backend/rag/pipeline/chunk.py`의 `DOC_DEFAULTS`(`collected_at`), 출처 주소는 manifest의 `source_url`에 있습니다. 평가자는 `python -m backend.rag.pipeline.collect download data/manifest.jsonl <pdf 폴더>`로 같은 PDF를 받습니다. 파일 합계가 수십 MB를 넘으면 강사에게 먼저 물어보세요.

## manifest 형식 (한 줄에 하나)

```json
{"doc_id":"tsc-1n4148-series_k2301","title":"1N4148 SERIES","revision":"K2301","source_url":"https://services.taiwansemi.com/storage/resources/datasheet/1N4148 SERIES_K2301.pdf","sha256":"cb6f27...","bytes":381862,"pages":5,"chunks":45,"chars_original":3752,"chars_kept":3601,"truncated":true}
```

모든 문서에 같은 값(`manufacturer`, `collected_at`, `parser`, `status`, `purpose`, `usage_conditions`)은 줄마다 쓰지 않고 `backend/rag/pipeline/chunk.py`의 `DOC_DEFAULTS`에 두며, `backend/rag/pipeline/ingest.py`가 읽을 때 채웁니다. 이 값과 다른 문서(다른 제조사, 아직 없는 `injection_tests/`)는 줄에 그 키를 적으면 줄의 값이 앞섭니다. 파일 이름이 `source_url` 끝과 다른 문서는 `path`를 적습니다.

manifest는 **512,000바이트 아래**로 둡니다. Checkpoint 대시보드가 1,012,774바이트 manifest를 "커서 읽지 못함"으로 표시했고(11-02), GitHub GraphQL은 파일 내용을 512,000바이트에서 자릅니다. `tests/rag/test_rag_chunk.py`가 크기를 확인합니다.

v1 manifest에서 청크에 들어가지 못한 원문 글자가 있으면 `chars_kept`가 `chars_original`보다 작고 `truncated`가 true입니다(2026-11-01 v1 스냅샷: TSC 1,360건 중 1,356건). 이 수치는 현재 v4h 청킹 통계가 아닙니다. 당시 TSC 코퍼스에서 `chars_original`은 Docling 본문(머리글·바닥글 제외) 글 조각과 표 칸의 글자 수, `chars_kept`는 그중 청크에 들어간 글자 수였습니다. 현재 청커의 보존 여부는 새 manifest와 `chunks.jsonl`로 다시 확인합니다.

청크 단위 기록은 `backend/rag/pipeline/chunk.py`가 만드는 `chunks.jsonl`(저장소 밖 로컬)에 있고, 청크마다 문서(`doc`)·순번(`idx`)·쪽·표·본문 해시(`sha256`)를 적습니다. 청크 수의 합이 1만을 넘고 **서로 다른 본문 해시가 1만 개 이상**이라는 것이 G3의 증거입니다. 같은 문구가 여러 문서에 나오면 해시가 같으므로 한 개로 셉니다.

## 임베딩 다시 하기

매번 전체를 다시 임베딩하지 말고 본문 해시가 바뀐 청크만 다시 합니다. `backend/rag/pipeline/ingest.py`가 본문 해시 캐시를 다시 씁니다.

## 저장소 크기 주의

현재 서비스 임베딩은 `voyage-4-large` 1024차원입니다. `text-embedding-3-small` 1536차원 행은 복구·과거 비교용으로 같은 표에 남길 수 있고, `db/008_multi_dim_embeddings.sql`은 두 차원을 함께 담는 차원 없는 `halfvec` 열로 전환합니다. 청크 본문과 벡터는 저장소에 넣지 않고 DB에만 둡니다(SPEC 6절, ADR 0005). 예외는 키 없는 데모용 스냅샷 `demo/snapshot/`의 청크 1,556개(벡터 없음)입니다.
