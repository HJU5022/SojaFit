# 운영 DB 청크 본문 직접 대조 (2026-11-16)

G3 증거. 강사 11/13 · 11/16 게이트 주의 "행 수 조회 기록이 생겼고 DB 값을 직접 열어 확인하는 일이 남았습니다"에 대한 기록이다. 11-13 [행 수 조회](index_row_count_2026-11-13.md)는 DB에 저장된 `chunk_sha256` 열을 셌을 뿐 본문을 다시 해시하지 않았다. 이번에는 운영 DB의 청크 본문(`content`) 51,967개를 모두 읽어 sha256을 DB 안에서 다시 계산하고, 저장소의 해시 목록과 대조했다.

## 결과 [실측]

- 대상: Cloud Run 운영 서비스가 쓰는 DB(Secret Manager `DATABASE_URL_NEW`, Supabase 프로젝트 `SojaFit_2`), DB `postgres`
- 시각: 2026-11-16 00:38:26 UTC (09:38 KST)
- 방법: 읽기 전용 연결(`read_only`)로 아래 쿼리를 실행하고 끝에 롤백했다. 쓰기는 없다. DB 주소는 셸 변수로만 넘기고 출력 · 파일에 남기지 않았다.

| 항목 | 값 |
|---|---|
| `document_chunks` 행 | 51,967 |
| 본문에서 다시 계산한 sha256이 저장된 `chunk_sha256`과 같은 행 | **51,967 / 51,967** |
| 다시 계산한 sha256의 서로 다른 값 | **51,967** (본문이 같은 청크 없음) |
| `chunker_version` | `tsc-v4h-2026-11-08` 하나 |
| DB에서 다시 계산한 해시 51,967개를 정렬해 줄바꿈으로 이은 글의 sha256 | `82dff159a6790631ae80d21b8e5aa10549dc54faffd914062c660526214ae677` |
| 저장소 [`chunk_sha256.tsv`](../chunking/v4h-2026-11-08/chunk_sha256.tsv)(51,967행)의 sha256 열로 같은 방법으로 만든 값 | `82dff159a6790631ae80d21b8e5aa10549dc54faffd914062c660526214ae677` |
| 두 값이 같은가 | **같다** |

뜻: 운영 DB의 청크 본문 집합은 저장소 해시 목록의 51,967개와 정확히 같다. 본문이 깨졌거나 다른 청킹 결과가 섞였다면 첫째 줄이나 마지막 줄이 달라진다.

직접 연 행의 예(문서 키 첫 번째 문서 앞 6개, 본문 앞부분만):

| document_key | chunk_index | 쪽 | 저장 해시 = 재계산 | 본문 앞부분 |
|---|---|---|---|---|
| `tsc-1.5ke-series_o2104` | 0 | - | 같음 (`9dece7d9…`) | `[1.5KE SERIES_O2104.pdf] 이 데이터시트의 품번: 1.5KE10, 1.5KE100, …` |
| `tsc-1.5ke-series_o2104` | 1 | 1 | 같음 (`b92ce754…`) | `[1.5KE SERIES_O2104.pdf · 1쪽 · 제품 개요] 1.5KE SERIES / DO-201 / 1500W, 6.8V …` |
| `tsc-1.5ke-series_o2104` | 2 | 1 | 같음 | `[1.5KE SERIES_O2104.pdf · 1쪽 · FEATURES] AEC-Q101 qualified available …` |
| `tsc-1.5ke-series_o2104` | 3 | 1 | 같음 | `[1.5KE SERIES_O2104.pdf · 1쪽 · APPLICATIONS] Protect sensitive circuit …` |
| `tsc-1.5ke-series_o2104` | 4 | 1 | 같음 | `[1.5KE SERIES_O2104.pdf · 1쪽 · MECHANICAL DATA] Case: DO-201 …` |
| `tsc-1.5ke-series_o2104` | 5 | 1 | 같음 | `[1.5KE SERIES_O2104.pdf · 1쪽 · Devices for Bipolar Applications] For b…` |

이 6행의 저장 해시는 `chunk_sha256.tsv`의 `1.5KE SERIES_O2104.pdf` 0 · 1행 값과도 같다.

## 다시 보는 방법

Supabase 대시보드 → `SojaFit_2` → SQL Editor(또는 `psql "$DATABASE_URL"`):

```sql
BEGIN READ ONLY;
SELECT count(*) AS chunks,
       count(*) FILTER (WHERE encode(sha256(convert_to(content, 'UTF8')), 'hex') = chunk_sha256) AS recomputed_equal,
       count(DISTINCT encode(sha256(convert_to(content, 'UTF8')), 'hex')) AS distinct_recomputed,
       encode(sha256(convert_to(string_agg(encode(sha256(convert_to(content, 'UTF8')), 'hex'), E'\n'
              ORDER BY encode(sha256(convert_to(content, 'UTF8')), 'hex')), 'UTF8')), 'hex') AS sorted_digest,
       string_agg(DISTINCT chunker_version, ',') AS chunkers
FROM document_chunks;
ROLLBACK;
```

저장소 쪽 같은 값(저장소 루트에서):

```bash
tail -n +2 evals/results/chunking/v4h-2026-11-08/chunk_sha256.tsv | cut -f3 | LC_ALL=C sort | python3 -c "import sys,hashlib;print(hashlib.sha256('\n'.join(l.strip() for l in sys.stdin).encode()).hexdigest())"
```

## 한계

- 본문 해시만 대조했다. 임베딩 벡터 값(`chunk_embeddings`)이 그 본문에서 나왔는지는 다시 계산하지 않았다(Voyage 호출이 필요하다). 임베딩 행 수는 11-13 조회에서 51,967로 같았다.
- `chunk_sha256.tsv`의 문서 이름 · 순번과 DB의 `document_key` · `chunk_index`를 행마다 짝지어 보지는 않았다. 해시 집합이 같고 서로 다른 값이 51,967개라 본문 대응은 하나씩 맞는다.
