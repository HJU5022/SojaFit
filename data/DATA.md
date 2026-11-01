# data

## 역할
- 이 폴더: 코퍼스 원문 스냅샷과 그 목록(manifest·청크·파라미터), 평가·시연용 회로, 데모 모드 응답을 둡니다. Dockerfile이 이 폴더를 이미지에 복사합니다.
- 넣는 것: 데이터시트·공개 문서 원본, `manifest.jsonl`(문서 단위), `chunks.jsonl`(청크 단위), `params.jsonl`(표에서 뽑은 파라미터와 쪽·표·행), 공개 KiCad 회로, 데모 응답.
- 넣지 않는 것: 데이터를 만드는 코드(`backend/rag/`), 평가셋(`evals/`), 단위 테스트용 가공 회로(`tests/fixtures/`), 실제 API 응답 원본.
- 담당: 검색·데이터 (`circuits/`는 평가·문서, `demo/`는 서비스·운영)

## 파일
- `corpus/` — 원본 문서. 출처별 하위 폴더는 [corpus/CORPUS.md](corpus/CORPUS.md)
- `circuits/` — 평가·시연용 공개 KiCad 회로. [circuits/CIRCUITS.md](circuits/CIRCUITS.md)
- `demo/` — 키 없이 도는 데모 모드가 재생하는 응답. [demo/DEMO.md](demo/DEMO.md)
- `manifest.jsonl` — 수집한 데이터시트 PDF의 출처·개정판·해시·페이지 수·파싱 상태. 현재 chunks=0은 아직 청킹하지 않았다는 뜻이다.

## 기준

G3: **서로 다른 청크 1만 개 이상, 서로 다른 문서 50건 이상**(복제와 변형 제외), 문서 파싱 1종 이상. 2만 개 이상을 권장합니다.

수집한 날짜와 출처 주소를 기록하세요. 서버에서 호출이 막히는 소스를 피하고, 평가자가 같은 코퍼스로 재현하기 위해서입니다. 파일 합계가 수십 MB를 넘으면 강사에게 먼저 물어보세요.

## manifest 형식 (한 줄에 하나)

```json
{"doc_id": "doc-0001", "source_url": "https://...", "collected_at": "2026-11-02", "parser": "pdf", "chunks": 214, "chars_original": 53210, "chars_kept": 53210, "truncated": false}
```

원문이 길어서 잘라 넣었다면 `chars_original`과 `chars_kept`가 다르고 `truncated`가 true여야 합니다. 얼마나 잘랐는지 숨기면 파싱 대조가 의미가 없어집니다.

청크 단위 기록이 필요하면 `chunks.jsonl`을 따로 두고 `doc_id`와 `chunk_id`, 위치, 본문 해시(`chunk_sha256`)를 적으세요. 청크 수의 합이 1만을 넘고 **서로 다른 `chunk_sha256`이 1만 개 이상**이라는 것이 G3의 증거입니다. 정정공시처럼 본문이 같은 문서는 해시가 같으므로 한 개로 셉니다.

## 임베딩 시간과 비용의 기준 (참고)

DART 공시 11,022청크(평균 762토큰) 기준입니다. 조 코퍼스에서는 반드시 100건으로 먼저 재 보세요.

| 방식 | 시간 또는 비용 |
|---|---|
| 로컬 KURE-v1 (Apple MPS, 배치 16) | 361초 (30.5청크/초). CPU 전용은 측정하지 않았습니다 |
| OpenAI text-embedding-3-small API | 1만 청크 한 번에 약 $0.15 ($0.02/1M 토큰). 매일 전체를 다시 하면 한 달 약 $4.6 |

매번 전체를 다시 임베딩하지 말고 본문 해시가 바뀐 청크만 다시 하세요.

## 저장소 크기 주의

벡터는 1024차원이면 1만 개에 약 41MB입니다. 본문과 manifest는 저장소에 두고, 벡터는 `db/` 아래 SQL로 적재하는 방법을 강사와 상의하세요.
