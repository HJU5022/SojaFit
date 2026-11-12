# D9 · 저장소 밖 증거 이관 (2026-11-11)

상태: **이관함**(청크 본문·`judge_items_full`·표주석 216건 원시 점검 파일은 제외). EVAL_REPORT §5 · §1 · §3-C가 가리키던 「저장소 밖」을 레포 경로로 바꾼다.

## Why

D9(검색 실패 유형 · 개선 근거)와 강사 지적(§5 원인·v4h manifest)은 위키·lab에만 있던 원본을 조 저장소에서 열 수 있어야 한다.

## 이관한 것 (A~D)

| | 내용 | 레포 경로 | 출처 |
|---|---|---|---|
| **A** | #39·#40 판정 길 문항별 진단 표 | [`evals/results/graph/2026-11-06-judge-diagnosis/`](../../evals/results/graph/2026-11-06-judge-diagnosis/) (`judge_items.md`·`.json`, `n04_n08_checks.json`) | 위키 `evidence/판정진단-2026-11-06/원본/` |
| **B** | v4h 표 파서 불일치 suspects 89건 + 요약 | [`evals/results/chunking/v4h-2026-11-08/table_suspects.jsonl`](../../evals/results/chunking/v4h-2026-11-08/table_suspects.jsonl) | 로컬 `corpus/tsc/chunks-v4h/` |
| **C** | v4h `summary.json` · `manifest.jsonl`(1,360행, 청크 본문 없음) | 같은 `v4h-2026-11-08/` | 동일 |
| **D** | #47 B 기준 · #48+#49 C 세트 원시 | [`evals/results/graph/2026-11-10-v3-outside/`](../../evals/results/graph/2026-11-10-v3-outside/) (`B-v3a/b`, `C-v3a/b`) | 위키 `evidence/v3측정-2026-11-10/원본/results/` |

sha256은 각 폴더 `SHA256.txt`.

### C 요약 숫자 `[실측]` (summary.json)

- 카드 51,967 · distinct_text 51,967 · chunker `tsc-v4h-2026-11-08`
- kinds: cover 1,360 · overview 1,348 · text 8,323 · table_row 38,385 · note 2,551
- tables_by_reader: pdfplumber 6,832 · docling 60 · table_suspects 89

### D 통과 요약 `[실측]` (각 set1.json `summary`)

| 실행 | 통과 | p50 · p95 |
|---|---|---|
| B-v3a (#47 구성) | 50/50 | 3.9 · 9.5 |
| B-v3b | 48/50 | 4.0 · 8.6 |
| C-v3a (#48+#49) | 50/50 | 3.8 · 9.0 |
| C-v3b | 49/50 | 4.7 · 9.9 |

#50·병합 뒤 2세트는 이미 [`evals/results/graph/2026-11-10-v3-haiku-sets/`](../../evals/results/graph/2026-11-10-v3-haiku-sets/)에 있음.

## 아직 없는 것

- **표 주석 216건(THERMAL 122 + 두 쪽 표 61 + 기타 32 + 오탐 1) 원시 점검 파일** — 위키 원장 「표 주석 붙기 점검 (11-09)」에 숫자만 있고 「원본 미이관」. `table_suspects.jsonl`은 **파서 불일치 89건**이라 216건과 다름 `[문서]`.
- `judge_items_full.json`(판정 노드 전문) · `chunks-v4h/chunks.jsonl`(~36MB) — 용량·본문 때문에 이번 이관에서 뺌.
- 범용 챗봇 대체재 5문항(EVAL_REPORT §10) — **11-12에 채움**(Codex 답 [`evals/results/graph/2026-11-12-codex-v3-50/`](../../evals/results/graph/2026-11-12-codex-v3-50/) · 표본 5행은 EVAL_REPORT §10).

## Out of Scope

청커 재실행, 운영 DB 재적재, 216건 재점검 스크립트 재실행.
