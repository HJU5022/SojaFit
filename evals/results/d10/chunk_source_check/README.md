# 표·수치 청크 vs 원본 PDF 쪽 텍스트 대조 (2026-11-13)

강사 요청(11/16까지 표·수치 청크를 원문과 직접 대조해 기록)에 대한 기록이다. 모두 로컬에서 읽기만 했다(운영 DB, 다운로드, API 호출 없음).

## 입력 (기존 증거 위에 쌓음)
- 청크 본문: `../corpus/tsc/chunks-v4h/chunks.jsonl` (51,967개). 실행 때마다 본문 sha256을 `evals/results/chunking/v4h-2026-11-08/chunk_sha256.tsv`와 51,967줄 전부 대조하고(불일치 0), 어긋나면 중단한다. 즉 채택된 해시 목록과 같은 본문이다.
- 원본 PDF: `../corpus/tsc/pdf/<doc>` (표본 116개 문서 모두 존재). **PDF 자체의 sha256을 `data/manifest.jsonl`과 대조하지는 않았다.**
- `data/demo/snapshot/chunks.jsonl`(1,556개, 42문서)은 문서·카테고리 폭이 좁아 쓰지 않고 전체 v4h에서 뽑았다.

## 방법
1. 대상: `kind=table_row`, 표 종류가 ratings(ABSOLUTE MAXIMUM RATINGS) · electrical(ELECTRICAL …) · thermal(THERMAL PERFORMANCE)이고 수치가 1개 이상 있는 청크.
2. 표본: (카테고리 14 × 표 종류 3) 칸마다 시드 1116으로 최대 3개, 총 **123개**(116문서, 14개 카테고리 전부; ratings 42 · electrical 42 · thermal 39. esd-protection은 칸이 비어 6개). 재현: `.venv/bin/python scripts/eval/chunk_source_check.py --seed 1116 --per-cell 3`
3. 대조: `pdfplumber`로 청크의 `page`쪽 텍스트만 추출(유니코드 마이너스 정규화). 청크의 값 필드(VALUE/TYP/MAX/MIN/CONDITIONS/품번 열 등)에서 숫자(음수 부호 포함, 쉼표 제거)를 모두 뽑아 그 쪽에 있는지, UNIT 문자열이 그 쪽에 있는지, 품번 열 이름(예: `152G`)이 있는지 본다. 하나라도 없으면 mismatch.
4. 행 근접(`row_window_ok`): 청크의 모든 숫자가 PDF 텍스트의 연속 6줄 안에 함께 있는가. 쪽 전체 일치보다 강한 보조 검사.
5. 제외: 본문의 `주:` 각주(알려진 한계: 표 각주 216건이 행에 붙지 않음), PARAMETER·SYMBOL·마킹코드 같은 글자 필드(숫자 검사 안 함).

## 결과
| 항목 | 값 |
|---|---|
| 표본 | 123 |
| match | **123** |
| mismatch | **0** |
| match인데 행 근접 실패 | 0 |

### mismatch 분류 (정직한 기록)
- **최종 0건.** 다만 첫 실행에서는 8건이 나왔고 전부 검사기 오탐이었다. 숨기지 않고 적는다: 원인은 (a) PDF 머리글에서 품번이 접두·접미로 갈라져 나오는 것(`FR` / `151G`), (b) 긴 머리글 라벨(`Test Current IT (mA)`)을 "값"으로 취급한 검사 설계 오류였다. 숫자·단위 불일치는 한 건도 없었다. 수정: 품번 열은 접미만 확인하고 긴 라벨은 검사에서 뺐다. 청크 오류(real error)로 분류된 것은 0건이다.

### 검사기의 한계 (음성 대조, 결과 `summary.json`의 `negative_control`)
숫자 하나의 끝자리를 +1로 바꾼 가짜 청크 110개로 검사기를 시험했다: 쪽 수준에서 91개(83%), 6줄 창 수준에서 95개(86%)만 잡혔다. 나머지는 바뀐 숫자가 같은 쪽 다른 곳에 우연히 있어 통과한다(예: `IF: 50`이 제목 "50A"와도 일치). 따라서 "0건 mismatch"는 **쪽에 없는 숫자가 청크에 있는 오류는 없다**는 뜻이고, 같은 쪽 다른 행의 값으로 바뀐 오류까지 배제하지는 못한다. (2026-11-16 보강: 같은 123개에 행 · 열 대조를 더한 결과는 [chunk_source_check_rows_2026-11-16](../chunk_source_check_rows_2026-11-16/README.md). 이 폴더의 결과는 그대로 둔다.)

## 확인하지 못한 것
- 123개 표본을 사람이 하나씩 눈으로 대조하지 않았다(자동 검사 + 4개 수동 확인: GBJ50JG, MURF1620CT, SF801G, UGF12JD).
- 행·열 단위 정밀 대조(품번별 열 값이 정확히 그 품번 열에서 왔는지)는 PDF 텍스트 추출이 열 구조를 잃어 못 했다. 이를 하려면 표 좌표 기반 대조나 이미지 육안 확인이 필요하다.
- 나머지 약 38,000개 표 행(표본 비율 0.3%), ORDERING·DIM 등 다른 표 종류, PDF 파일 sha256 대조, 표 각주 216건(행에 안 붙은 상태 그대로).
- 스캔·이미지 표(텍스트 추출 불가)는 표본에서 걸리지 않았다.

## 파일
- `results.jsonl`: 청크별 doc, idx, page, row, text, 검사한 값, result, row_window_ok, mismatch 내역
- `summary.json`: 집계와 음성 대조
- 스크립트: `scripts/eval/chunk_source_check.py`
