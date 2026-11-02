# data

## 역할
- 이 폴더: 코퍼스 원문 표본 3건과 문서 목록(manifest), 평가·시연용 회로, 데모 모드 응답을 둡니다. 코퍼스 원본 PDF·파싱 결과·청크는 저장소 밖 로컬 `SojaFit/corpus/tsc/`에 둡니다. Dockerfile이 이 폴더를 이미지에 복사합니다.
- 넣는 것: 데이터시트 원본 표본(`corpus/tsc/` 3건)·공개 문서 원본, `manifest.jsonl`(문서 단위), `params.jsonl`(표에서 뽑은 파라미터와 쪽·표·행), 공개 KiCad 회로, 데모 응답.
- 넣지 않는 것: 데이터를 만드는 코드(`backend/rag/`), 평가셋(`evals/`), 단위 테스트용 가공 회로(`tests/fixtures/`), 실제 API 응답 원본.
- 담당: 검색·데이터 (`circuits/`는 평가·문서, `demo/`는 서비스·운영)

## 파일
- `corpus/` — 원본 문서 표본. 출처별 하위 폴더는 [corpus/CORPUS.md](corpus/CORPUS.md)
- `circuits/` — 평가·시연용 공개 KiCad 회로. [circuits/CIRCUITS.md](circuits/CIRCUITS.md)
- `demo/` — 키 없이 도는 데모 모드가 재생하는 응답. [demo/DEMO.md](demo/DEMO.md)
- `manifest.jsonl` — 코퍼스 데이터시트 PDF 1,360건의 출처·개정판·해시·쪽 수·카드 수. `backend/rag/chunk.py`가 쓴다. 원래 PDF 파일 이름은 `source_url` 끝에 있고, PDF는 저장소 밖 로컬 `SojaFit/corpus/tsc/pdf/`에 있다

## 기준

G3: **서로 다른 청크 1만 개 이상, 서로 다른 문서 50건 이상**(복제와 변형 제외), 문서 파싱 1종 이상. 정본은 [docs/GATES.md](../docs/GATES.md)입니다.

수집일은 `backend/rag/chunk.py`의 `DOC_DEFAULTS`(`collected_at`), 출처 주소는 manifest의 `source_url`에 있습니다. 평가자는 `python -m backend.rag.collect download data/manifest.jsonl <pdf 폴더>`로 같은 PDF를 받습니다. 파일 합계가 수십 MB를 넘으면 강사에게 먼저 물어보세요.

## manifest 형식 (한 줄에 하나)

```json
{"doc_id":"tsc-1n4148-series_k2301","title":"1N4148 SERIES","revision":"K2301","source_url":"https://services.taiwansemi.com/storage/resources/datasheet/1N4148 SERIES_K2301.pdf","sha256":"cb6f27...","bytes":381862,"pages":5,"chunks":45,"chars_original":3752,"chars_kept":3601,"truncated":true}
```

모든 문서에 같은 값(`manufacturer`, `collected_at`, `parser`, `status`, `purpose`, `usage_conditions`)은 줄마다 쓰지 않고 `backend/rag/chunk.py`의 `DOC_DEFAULTS`에 두며, `backend/rag/ingest.py`가 읽을 때 채웁니다. 이 값과 다른 문서(다른 제조사, `injection_tests/`)는 줄에 그 키를 적으면 줄의 값이 앞섭니다. 파일 이름이 `source_url` 끝과 다른 문서는 `path`를 적습니다.

manifest는 **512,000바이트 아래**로 둡니다. Checkpoint 대시보드가 1,012,774바이트 manifest를 "커서 읽지 못함"으로 표시했고(11-02), GitHub GraphQL은 파일 내용을 512,000바이트에서 자릅니다. `tests/test_rag_chunk.py`가 크기를 확인합니다.

카드에 들어가지 못한 원문 글자가 있으면 `chars_kept`가 `chars_original`보다 작고 `truncated`가 true입니다(TSC 1,360건 중 1,356건). TSC 코퍼스에서 `chars_original`은 Docling 본문(머리글·바닥글 제외) 글 조각과 표 칸의 글자 수, `chars_kept`는 그중 카드에 들어간 글자 수입니다(`backend/rag/chunk.py`). 얼마나 잘랐는지 숨기면 파싱 대조가 의미가 없어집니다.

카드 단위 기록은 `backend/rag/chunk.py`가 만드는 `chunks.jsonl`(저장소 밖 로컬)에 있고, 카드마다 문서(`doc`)·순번(`idx`)·쪽·표·본문 해시(`sha256`)를 적습니다. 청크 수의 합이 1만을 넘고 **서로 다른 본문 해시가 1만 개 이상**이라는 것이 G3의 증거입니다. 같은 문구가 여러 문서에 나오면 해시가 같으므로 한 개로 셉니다.

## 임베딩 다시 하기

매번 전체를 다시 임베딩하지 말고 본문 해시가 바뀐 카드만 다시 합니다. `backend/rag/ingest.py`가 본문 해시 캐시를 다시 씁니다.

## 저장소 크기 주의

벡터는 1536차원(`text-embedding-3-small`, ADR 0004 임시 결정)이라 카드 52,244장이면 float32로 약 321MB, halfvec으로 약 160MB입니다(계산). 카드 본문과 벡터는 저장소에 넣지 않고 DB에만 둡니다(SPEC 6절, ADR 0005).
