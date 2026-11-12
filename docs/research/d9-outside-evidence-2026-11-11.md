# D9 근거 자료: 저장소 안으로 옮긴 원시 목록

- 상태: 현행
- 기준일: 2026-11-11
- 기준 커밋: 6707002 (경로 존재와 수치 재확인 시점)
- 정본 여부: 정본(D9 근거 자료의 저장소 경로 색인). 수치의 정본은 각 폴더의 원시 파일, 평가 서술은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 5절·1절·3-C
- 관련 문서: [EVAL_REPORT.md](../../EVAL_REPORT.md), [docs/GATES.md](../GATES.md)

## 1. 범위

D9(검색 실패 유형과 개선 근거)가 인용하는 원시 자료 중 저장소 안으로 옮긴 것 4건(A~D)과 아직 없는 것 3건. 청크 본문, `judge_items_full`, 표 주석 216건의 원시 점검 파일은 옮기지 않았다.

## 2. 항목

각 폴더의 sha256은 해당 폴더 `SHA256.txt`에 있다.

| | 내용 | 저장소 경로 | 파일 |
|---|---|---|---|
| A | #39·#40 판정 길 문항별 진단 | [evals/results/graph/2026-11-06-judge-diagnosis/](../../evals/results/graph/2026-11-06-judge-diagnosis/) | `judge_items.md`, `judge_items.json`, `n04_n08_checks.json` |
| B | v4h 표 파서 불일치 suspects 89건 | [evals/results/chunking/v4h-2026-11-08/table_suspects.jsonl](../../evals/results/chunking/v4h-2026-11-08/table_suspects.jsonl) | 89행 |
| C | v4h `summary.json`, `manifest.jsonl`(1,360행, 청크 본문 없음) | [evals/results/chunking/v4h-2026-11-08/](../../evals/results/chunking/v4h-2026-11-08/) | |
| D | #47 B 기준, #48+#49 C 세트 원시 | [evals/results/graph/2026-11-10-v3-outside/](../../evals/results/graph/2026-11-10-v3-outside/) | `B-v3a`, `B-v3b`, `C-v3a`, `C-v3b` |

#50과 병합 뒤 2세트는 [evals/results/graph/2026-11-10-v3-haiku-sets/](../../evals/results/graph/2026-11-10-v3-haiku-sets/)에 있다.

### 2.1 C의 요약 숫자 (`summary.json`)

| 항목 | 값 |
|---|---|
| 카드 / distinct_text | 51,967 / 51,967 |
| chunker | `tsc-v4h-2026-11-08` |
| kinds | cover 1,360, overview 1,348, text 8,323, table_row 38,385, note 2,551 |
| tables_by_reader | pdfplumber 6,832, docling 60 |
| table_suspects | 89 |

### 2.2 D의 통과 요약 (각 `set1.json`의 `summary`)

| 실행 | 구성 | 통과 | p50 / p95 (초) | 기준 커밋 |
|---|---|---|---|---|
| B-v3a | #47 | 50/50 | 3.9 / 9.5 | 4a61fd0 |
| B-v3b | #47 | 48/50 | 4.0 / 8.6 | 4a61fd0 |
| C-v3a | #48+#49 | 50/50 | 3.8 / 9.0 | 5d37cd0 |
| C-v3b | #48+#49 | 49/50 | 4.7 / 9.9 | 5d37cd0 |

## 3. 한계

| 없는 것 | 상태 |
|---|---|
| 표 주석 216건(THERMAL 122, 두 쪽 표 61, 기타 32, 오탐 1)의 원시 점검 파일 | 숫자만 있고 원시가 저장소에 없다. `table_suspects.jsonl`은 파서 불일치 89건이며 216건과 다르다 |
| `judge_items_full.json`(판정 노드 전문), `chunks-v4h/chunks.jsonl`(약 36MB) | 용량과 청크 본문 때문에 옮기지 않았다 |
| A~D의 이관 전 원본 | 저장소 밖(위키, 로컬 `corpus/tsc/chunks-v4h/`)에 있었다. 저장소의 사본이 유일한 열람 경로다 |

범용 챗봇 대체재 5문항은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 10절에 있다. Codex 답은 [evals/results/graph/2026-11-12-codex-v3-50/](../../evals/results/graph/2026-11-12-codex-v3-50/), 입력은 [evals/guides/v3_50_codex_paste.md](../../evals/guides/v3_50_codex_paste.md).

범위 밖: 청커 재실행, 운영 DB 재적재, 216건 재점검 스크립트 실행.
