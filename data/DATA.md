# data

## 역할
- 이 폴더: 서비스·평가가 읽는 고정 데이터를 둔다. 코퍼스 문서 목록(`manifest.jsonl`), 패키지 외형 페이지 색인, 코퍼스 원본 표본, 평가·시연용 공개 회로, 키 없는 데모의 코퍼스 스냅샷과 LLM 응답 기록(`demo/`)이 있다. Dockerfile이 이 폴더를 이미지에 복사한다.
- 넣는 것: `manifest.jsonl`(문서 단위 목록), 데이터시트 원본 표본(`corpus/tsc/` 3건), 공개 KiCad 회로(`circuits/`), 키 없는 데모 자료(`demo/`: compose가 로컬 DB에 넣는 코퍼스 스냅샷 `demo/snapshot/`, 재생할 LLM 응답 기록 `demo/recordings/`).
- 넣지 않는 것: 데이터시트 PDF 전체 1,360건·파싱 결과(`docling` 산출물)·전체 청크(`chunks.jsonl`, 데모 스냅샷 `demo/snapshot/`만 예외)·임베딩 캐시(저장소 밖 작업 자료), 데이터를 만드는 코드(`backend/rag/`), 평가셋(`evals/`), 단위 테스트용 가공 회로(`tests/` 아래), 실제 API 응답 원본.
- 담당: 검색·데이터 (`circuits/`는 평가·문서, `demo/`는 서비스·운영)
- 정본: 코퍼스 문서·쪽·청크 수는 이 문서의 "코퍼스 수치" 표.

전체 PDF·파싱·청크·임베딩 산출물은 저장소에 없다. 저장소에서 확인할 수 있는 것은 `manifest.jsonl`, PDF 표본 3건, 데모 스냅샷, `evals/results/chunking/v4h-2026-11-08/`의 요약·manifest·청크별 sha256 목록이다.

## 파일

| 파일·폴더 | 유형 | 설명 |
|---|---|---|
| `DATA.md` | 폴더 설명 | 이 문서 |
| `manifest.jsonl` | 데이터 | 이전 버전(v1) 청킹 당시의 코퍼스 문서 목록. 현재 코퍼스는 v4h(아래 "코퍼스 수치"). 문서 단위(id, 판본, 출처, sha256, 쪽 수, 청크 수) 1,360줄. 원래 PDF 파일 이름은 `source_url` 끝 |
| `package-outline-pages.json` | 데이터 | manifest 1,360문서의 공식 URL과 Docling 표제·그림이 같은 최초 패키지 외형 페이지를 URL-decoded PDF basename으로 찾는 오프라인 색인 |
| `corpus/` | 폴더 | 코퍼스 원본 문서 표본(TSC PDF 3건)과 시험용 합성 자료. [CORPUS.md](corpus/CORPUS.md) |
| `circuits/` | 폴더 | 평가·시연용 공개 KiCad 회로와 라이선스. [CIRCUITS.md](circuits/CIRCUITS.md) |
| `demo/` | 폴더 | 키 없는 데모의 코퍼스 스냅샷(`snapshot/`)과 LLM 응답 기록(`recordings/`). [DEMO.md](demo/DEMO.md) |

## 코퍼스 수치

문서·쪽·청크 수의 정본이다. 다른 문서는 이 표를 링크한다. 현재 코퍼스는 v4h 청킹(청크 51,967)이다. `data/manifest.jsonl`(청크 52,244)은 이전 버전(v1) 청킹의 문서 목록이다.

| 항목 | 이전 버전(v1) 청킹: `data/manifest.jsonl` | 현재 코퍼스, v4h 청킹: `evals/results/chunking/v4h-2026-11-08/` | 데모 스냅샷: `data/demo/snapshot/manifest.jsonl` |
|---|---:|---:|---:|
| 문서 | 1,360 | 1,360 | 42 |
| 쪽 | 7,725 | 7,725 | 211 |
| 청크 | 52,244 | 51,967 | 1,556 |
| 서로 다른 본문 | 45,898 | 51,967 | 1,556 |
| 청커 버전 | manifest에 없음 | `tsc-v4h-2026-11-08` | `tsc-v4h-2026-11-08` |
| 계산 방법 | manifest 각 줄의 `pages`·`chunks` 합 | `manifest.jsonl` 각 줄의 합. `summary.json`의 `cards`·`distinct_text`도 51,967 | `manifest.jsonl` 각 줄의 합 |
| 서로 다른 본문의 근거 | 저장소에서 재계산 불가. 값의 출처는 [GATES.md](../docs/GATES.md) G3 | `summary.json`의 `distinct_text`, 청크별 sha256 목록의 서로 다른 해시 51,967 | [SNAPSHOT.md](demo/snapshot/SNAPSHOT.md) |

- 두 manifest의 `bytes` 합은 같다: 626,919,120 (PDF 1,360건).
- v4h 청크 본문은 저장소에 없다(약 36MB, `evals/results/chunking/v4h-2026-11-08/README.md`). 파일별 sha256은 같은 폴더의 `SHA256.txt`와 [corpus_v4h_fingerprint_2026-11-12.md](../evals/results/d10/corpus_v4h_fingerprint_2026-11-12.md).
- v4h 청크별 sha256 목록(51,967행, 본문 없음): [chunk_sha256.tsv](../evals/results/chunking/v4h-2026-11-08/chunk_sha256.tsv). 해시 대상·줄바꿈(LF)·확인 및 재생성 명령·`chunks.jsonl` 입수는 [chunk_sha256.md](../evals/results/chunking/v4h-2026-11-08/chunk_sha256.md).
- 데모 스냅샷 manifest 42줄은 v4h `manifest.jsonl`의 같은 줄과 일치한다. 스냅샷이 적어 둔 원본 manifest sha256(`426b4475…`)은 `evals/results/chunking/v4h-2026-11-08/manifest.jsonl`의 sha256과 같다 [실측].

서비스가 쓰는 코퍼스:

| 환경 | 코퍼스 | 근거 |
|---|---|---|
| 키 없는 데모(`DEMO_MODE=1`) | 데모 스냅샷(v4h에서 뽑은 42문서, 청크 1,556) | [SNAPSHOT.md](demo/snapshot/SNAPSHOT.md) "적재와 쓰는 곳" |
| 운영 DB | [GATES.md](../docs/GATES.md) G3가 문서 1,360 · 청크 51,967로 기록(2026-11-11). 이 값을 운영 DB에서 다시 센 기록은 저장소에 없고, 이 저장소 파일만으로는 운영 DB가 위 두 manifest 중 어느 것과 같은지 확인할 수 없다 | `docs/GATES.md` G3 |

## 기준

G3: 서로 다른 청크 1만 개 이상, 서로 다른 문서 50건 이상(복제와 변형 제외), 문서 파싱 1종 이상. 정본은 [docs/GATES.md](../docs/GATES.md).

수집일은 `backend/rag/pipeline/chunk.py`의 `DOC_DEFAULTS`(`collected_at`), 출처 주소는 manifest의 `source_url`에 있다. 같은 PDF는 `python -m backend.rag.pipeline.collect download data/manifest.jsonl <pdf 폴더>`로 받는다. PDF 1,360건은 합계 626,919,120바이트(약 627 MB)로 수십 MB를 크게 넘으므로 받기 전에 확인한다.

## manifest 형식 (한 줄에 하나)

```json
{"doc_id":"tsc-1n4148-series_k2301","title":"1N4148 SERIES","revision":"K2301","source_url":"https://services.taiwansemi.com/storage/resources/datasheet/1N4148 SERIES_K2301.pdf","sha256":"cb6f27...","bytes":381862,"pages":5,"chunks":45,"chars_original":3752,"chars_kept":3601,"truncated":true}
```

- 모든 문서에 같은 값(`manufacturer`, `collected_at`, `parser`, `status`, `purpose`, `usage_conditions`)은 줄마다 쓰지 않고 `backend/rag/pipeline/chunk.py`의 `DOC_DEFAULTS`에 둔다. `backend/rag/pipeline/ingest.py`가 읽을 때 채운다. 이 값과 다른 문서(다른 제조사, `injection_tests/`)는 줄에 그 키를 적으면 줄의 값이 앞선다. 파일 이름이 `source_url` 끝과 다른 문서는 `path`를 적는다.
- 크기: `data/manifest.jsonl`은 512,000바이트 아래로 둔다. GitHub GraphQL이 파일 내용을 512,000바이트에서 자른다. 현재 470,263바이트 [실측]. `tests/rag/test_rag_chunk.py`가 크기를 확인한다.
- `chars_kept`가 `chars_original`보다 작고 `truncated`가 true이면 청크에 들어가지 못한 원문 글자가 있다. v1 manifest는 1,360건 중 1,356건이 true [실측]. `chars_original`은 Docling 본문(머리글·바닥글 제외) 글 조각과 표 칸의 글자 수이고 `chars_kept`는 그중 청크에 들어간 글자 수다.
- 청크 단위 기록은 `backend/rag/pipeline/chunk.py`가 만드는 `chunks.jsonl`(저장소 밖)에 있다. 청크마다 문서(`doc`)·순번(`idx`)·쪽·표·본문 해시(`sha256`)가 있다. 같은 문구가 여러 문서에 나오면 해시가 같으므로 한 개로 센다. 서로 다른 본문 해시 1만 개 이상이 G3의 증거다.

## 임베딩 다시 하기

전체를 다시 임베딩하지 않고 본문 해시가 바뀐 청크만 다시 한다. `backend/rag/pipeline/ingest.py`가 본문 해시 캐시를 다시 쓴다.

## 저장소 크기

현재 서비스 임베딩은 `voyage-4-large` 1024차원이다. `text-embedding-3-small` 1536차원 행은 복구·과거 비교용으로 같은 표에 둘 수 있고, `db/008_multi_dim_embeddings.sql`은 두 차원을 함께 담는 차원 없는 `halfvec` 열로 전환한다. 청크 본문과 벡터는 저장소에 넣지 않고 DB에만 둔다(SPEC 6절, ADR 0005). 예외는 키 없는 데모용 스냅샷 `demo/snapshot/`의 청크 1,556개(벡터 없음)다.
