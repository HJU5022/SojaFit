# snapshot

## 역할
- 이 폴더: 키 없는 `docker compose up`이 로컬 pgvector DB의 문서·청크 표(`source_documents`·`document_chunks`)에 넣는 데모 코퍼스 스냅샷입니다. 데모 회로 두 개의 다이오드(Franzininho DIY의 D3 = 1N4148, Breadboard Power Supply의 D1 = 1N4001)와 그 대체 후보를 키 없이 BM25로 찾을 수 있게 고른 TSC 데이터시트 문서 42건, 청크 1,556개입니다.
- 넣는 것: 전체 v4h 청크에서 규칙대로 뽑은 `manifest.jsonl`·`chunks.jsonl`. 줄은 원본과 바이트까지 같고 `backend/rag/pipeline/ingest.py`가 읽는 형식 그대로입니다.
- 넣지 않는 것: 임베딩(키가 없으면 질문도 임베딩하지 못해 BM25만 씁니다), 전체 코퍼스 청크(저장소 밖), 원본 PDF(`data/corpus/`).
- 담당: 서비스·운영

## 파일

| 파일 | 줄 | 크기(바이트) | sha256 |
|---|---:|---:|---|
| `manifest.jsonl` | 문서 42줄 | 14,274 | `7acafe7700188b51951bd2fe37f88178b22324451a63f97a36e789739b4e3220` |
| `chunks.jsonl` | 청크 1,556줄 | 793,992 | `f65dbe5268dbbc229baad95eab6f51841f5b8178272f3783a228e5287e1301d7` |

청크 종류: 표 행 1,164 · 글 234 · 표 주석 74 · 품번 표지 42 · 제품 개요 42. 서로 다른 본문 sha256 1,556개. 원본 PDF 쪽 수 합계 211쪽.

## 출처
- 원본: 저장소 밖 `SojaFit/corpus/tsc/chunks-v4h/`의 `manifest.jsonl`(문서 1,360건, sha256 `426b44750dc6aae3634855da44b5a9de675fdc31fb9ee859fc55d772a8c0d786`)과 `chunks.jsonl`(청크 51,967개, sha256 `bc1454cfee189b3c73fabe82dcfc1f5861b5feddd9f9b65efa3f93c2a10cee17`).
- 문서: Taiwan Semiconductor(TSC) 다이오드 데이터시트. 문서마다 원본 PDF 주소는 `manifest.jsonl`의 `source_url`이고, 42건 모두 `https://services.taiwansemi.com/storage/resources/datasheet/<파일 이름>`입니다. 개정판은 `revision`, PDF sha256은 `sha256`에 있습니다.
- 청커 버전: `tsc-v4h-2026-11-08`(원본 `summary.json`의 `chunker_version`). 청크 줄에는 버전 칸이 없고, 적재할 때 `ingest.py`가 같은 값(`chunk.py`의 `CHUNKER_VERSION`)을 `document_chunks.chunker_version`에 넣습니다. `source_documents.corpus_version`에는 `ingest.py`에 고정된 `tsc-diode-2026-11-01`이 들어갑니다.
- 파서·수집일: `chunk.py`의 `DOC_DEFAULTS`(docling 2.145.0, OCR off, 2026-11-01).

## 이용 조건
- Taiwan Semiconductor 사이트 약관은 정보·비상업 목적에 한해, 고치지 않고 저작권 고지를 유지하고 출처를 밝히는 조건으로 복제·배포를 허용합니다([CORPUS.md](../../corpus/CORPUS.md)). 적재할 때 `source_documents.license_text`에는 `chunk.py`의 `USAGE` 문구가 들어갑니다.
- 이 파일들은 원본 PDF가 아니라 PDF를 파싱해 자른 청크 글(품번 표지·제품 개요·글·표 행·표 주석)입니다. SPEC 6절은 TSC 약관이 청크 저장·인용을 따로 다루지 않는다고 적습니다.

## 고른 규칙

문서의 품번 목록(`parts`)으로 고르고, 여러 규칙에 걸리면 앞 번호를 이유로 적습니다. 고른 문서의 청크는 자르지 않고 모두 넣었습니다.

| 규칙 | 내용 | 문서 |
|---|---|---:|
| 1 | 품번 `1N4148`이 있는 문서 | 1 |
| 2 | `1N4148`로 시작하는 다른 품번(1N4148W·1N4148WS·1N4148WH 등, 대체 후보)이 있는 문서 | 7 |
| 3 | `1N4001G`·`1N4007G`로 시작하는 품번이 있는 문서. 코퍼스에 1N4001은 없고 1N4001G·1N4001G-K만 있습니다 | 2 |
| 4 | 1번 문서와 분류 이름(`ingest.py`와 같은 `family()`)이 같은 `switching-diode`의 나머지 문서. 60건이 넘으면 파일 이름 순 앞 60건만 넣는 규칙이지만 분류 전체가 40건이라 모두 넣었습니다 | 32 |

## 문서 목록

| 규칙 | 파일 | 청크 |
|---:|---|---:|
| 1 | `1N4148 SERIES_K2301.pdf` | 46 |
| 2 | `1N4148W SERIES_K1804.pdf` | 53 |
| 2 | `1N4148W-G_D1601.pdf` | 42 |
| 2 | `1N4148WH_A2501.pdf` | 35 |
| 2 | `1N4148WS SERIES_N2212.pdf` | 46 |
| 2 | `1N4148WS-G_C2211.pdf` | 32 |
| 2 | `1N4148WSH_A2501.pdf` | 35 |
| 2 | `1N4148WTH_A2501.pdf` | 35 |
| 3 | `1N4001G SERIES_P2104.pdf` | 32 |
| 3 | `1N4001G-K SERIES_B2104.pdf` | 30 |
| 4 | `1SS355_D2212.pdf` | 32 |
| 4 | `1SS400_E2510.pdf` | 30 |
| 4 | `BAS116_F2001.pdf` | 32 |
| 4 | `BAS16H_A2412.pdf` | 39 |
| 4 | `BAS16_F2001.pdf` | 32 |
| 4 | `BAS19 SERIES_C2001.pdf` | 37 |
| 4 | `BAS19W SERIES_B14.pdf` | 34 |
| 4 | `BAS21 SERIES_E2001.pdf` | 42 |
| 4 | `BAS21H_A2412.pdf` | 36 |
| 4 | `BAS316WS_F2212.pdf` | 39 |
| 4 | `BAS316_E1907.pdf` | 30 |
| 4 | `BAV101 SERIES_E2301.pdf` | 30 |
| 4 | `BAV19W SERIES_E15.pdf` | 38 |
| 4 | `BAV19W-G SERIES_D1603.pdf` | 48 |
| 4 | `BAV19WS SERIES_K2212.pdf` | 40 |
| 4 | `BAV19WS-G SERIES_A15.pdf` | 38 |
| 4 | `BAV21WH_A2412.pdf` | 34 |
| 4 | `BAV23CH_A2501.pdf` | 38 |
| 4 | `BAV23SH_A2501.pdf` | 38 |
| 4 | `BAV70H_A2412.pdf` | 39 |
| 4 | `BAV70WH_A2412.pdf` | 35 |
| 4 | `BAV99H_A2412.pdf` | 39 |
| 4 | `BAV99WH_A2412.pdf` | 35 |
| 4 | `BAV99W_C2102.pdf` | 37 |
| 4 | `BAW56 SERIES_I2001.pdf` | 37 |
| 4 | `BAW56H_A2412.pdf` | 39 |
| 4 | `BAW56WH_A2412.pdf` | 36 |
| 4 | `LL4148 SERIES_K2301.pdf` | 45 |
| 4 | `MMBD3004 SERIES_C2001.pdf` | 36 |
| 4 | `MMBD4148 SERIES_F2112.pdf` | 38 |
| 4 | `TS4148 SERIES_A2301.pdf` | 31 |
| 4 | `TS4448 RG_H1612.pdf` | 36 |

## 다시 만들기와 확인

```bash
uv run python -m backend.rag.pipeline.demo_snapshot <chunks-v4h 폴더> data/demo/snapshot   # 다시 만들기
DEMO_SNAPSHOT_SOURCE=<chunks-v4h 폴더> uv run pytest tests/rag/test_demo_snapshot.py       # 다시 뽑은 바이트가 같은지까지 확인
```

`tests/rag/test_demo_snapshot.py`는 원본 없이도 두 파일의 sha256·문서·청크 수가 이 문서와 같은지, manifest 문서마다 청크가 0번부터 빠짐없이 있는지, 고르기 규칙(가짜 원본)을 늘 확인합니다. 원본에서 다시 뽑는 시험만 `DEMO_SNAPSHOT_SOURCE`가 있을 때 돕니다.

## 적재와 쓰는 곳
- Compose의 `corpus-load` 서비스가 DB healthcheck 뒤 `python -m backend.rag.pipeline.ingest data/demo/snapshot/manifest.jsonl data/demo/snapshot/chunks.jsonl /tmp/vectors --chunks-only`를 돌리고, api는 이 서비스가 성공한 뒤 시작합니다. 이미 있는 문서·청크는 건너뛰므로 다시 떠도 행이 늘지 않습니다.
- `DEMO_MODE=1`에서 검색(`backend/rag/retrieve.py`의 `retrieve`, MCP `search_corpus`)은 임베딩·리랭크 없이 BM25로 이 스냅샷을 찾습니다. 지금 React 작업대의 키 없는 분석(`DEMO_SCENARIOS=1`)은 합성 시나리오(`../scenarios.json`)로 답하고 이 스냅샷을 읽지 않습니다.
- 규모 게이트(G3, 서로 다른 청크 1만 개·문서 50건)는 이 스냅샷이 아니라 전체 코퍼스 manifest로 봅니다.
