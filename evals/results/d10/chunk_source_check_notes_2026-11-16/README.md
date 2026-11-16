# 표·수치 청크 대조: 부품 행 표와 표 각주 검사 추가 (2026-11-16)

강사 11/16 코멘트(축 ②)의 "먼저 할 것"인 "원문 대조에 각주와 부품 행 표를 포함하라"에 대한 기록이다. 사전 등록은 `evals/guides/preregister.md` 2026-11-16 "표·수치 청크 대조에 '부품 행 표'와 '표 각주' 검사 추가" 항목이다. 같은 도구(`scripts/eval/chunk_source_check.py`)에 `--notes`를 더해 지난번과 같은 123개 표본에 돌렸다. 로컬에서 읽기만 했고(DB·네트워크·유료 호출 없음), 기존 두 폴더(`../chunk_source_check/`, `../chunk_source_check_rows_2026-11-16/`)는 바꾸지 않았다. 코퍼스도 고치지 않았다.

## 명령
```bash
uv run --no-sync python scripts/eval/chunk_source_check.py --notes   # 결과 폴더 기본값이 이 폴더. --notes는 --rows를 포함
uv run --no-sync pytest -q tests/evals/test_chunk_source_check.py    # 변이 시험(합성 표, PDF 불필요), 17개 통과
```
입력은 지난번과 같다. v4h 청크 본문 51,967개(sha256을 `chunk_sha256.tsv`와 대조), `../corpus/tsc/pdf/`, 시드 1116, 칸당 3개. 실행 시간은 약 1분 40초다.
`--notes`에 `--out`으로 두 기존 폴더를 주면 쓰기 전에 멈춘다(`기존 결과 폴더는 덮어쓰지 않는다`, 종료 코드 1, 두 폴더 모두 확인).

## 새 검사가 하는 일

### 1. 부품 행 검사(`part_check`)
행 이름 칸(PARAMETER·CONDITIONS·SYMBOL)이 없는 청크만 본다. 행 이름 칸이 있으면 `null`이고, 그 청크는 `row_check`가 맡는다.
1. 청크의 첫 칸 값을 품번으로 본다(`Device: P6SMB100A`, `Part number / Uni: 5.0SMDJ28A`).
2. 쪽의 표마다 첫 데이터 행을 찾는다. 첫 칸에 숫자가 있고 다른 칸에 값(숫자나 `-`)이 있는 첫 행이다. 그 위에서 모든 칸이 같은 제목 행을 뺀 행들을 머리글로 본다.
3. 머리글은 열마다 위에서 아래로 잇는다. 세로 병합으로 같은 글자가 반복되면 한 번만 쓴다. 예: `Breakdown Voltage V (V) BR (Note 1) / Min`.
4. 첫 열이 품번과 공백·쉼표만 빼고 **정확히 같은** 행을 찾는다. `P6SMB100A`는 `P6SMB100` 행에 붙지 않는다.
5. 청크의 열 이름마다 머리글 문자 구성(Counter)이 같은 열을 찾는다. PDF는 아래첨자를 줄 끝으로 보내 `V (V)\nBR`과 `VBR (V)`처럼 순서가 다르다. 그 열 칸 값이 청크 값과 같은지 본다.
6. 판정은 `row_check`와 같다.
   - 다른 칸이 있으면 `row_mismatch`이고, `found_elsewhere`에 같은 행 다른 열 / 다른 행 같은 열을 적는다.
   - 행이 없거나, 같은 품번 행들의 결과가 갈리면 `unlocated`다.
   - 열을 못 찾거나 이름이 같은 열이 둘 이상인 칸은 `unchecked`에 적고 일치로 세지 않는다.

### 2. 각주 검사(`note_check`)
PDF에서 따로 읽는다. 청커 규칙은 쓰지 않는다. 대상 표·행은 `row_check`(행 이름)나 `part_check`(품번)가 찾은 것이다. 둘 다 못 찾으면 `unclear`다.

**표의 각주 묶음** (`page_notes` · `parse_notes`)
1. 그 표 bbox의 bottom부터 그 아래 다음 표의 top까지에서 표 밖 줄만 본다(pdfplumber `extract_text_lines`).
2. 그 첫 줄이 각주 머리여야 한다. 아니면 이 표에는 각주가 없다.
   - 머리 형식: `Notes:`, `Note:`, 앞말이 붙은 `Thermal Performance Note:`, 머리 줄 안 각주(`Notes: Units mounted …`), 줄마다 번호(`Note 1 : …`).
   - [왜] 청커의 `^notes?` 머리를 쓰지 않는 이유: 앞말이 붙은 머리를 받아야 한다.
3. 그 뒤 줄을 차례로 읽는다.
   - 번호 줄(`1. `, `(2) `, `Note 2 :`, `* `)은 새 각주다.
   - 머리보다 3pt 넘게 들여 쓴 줄은 앞 각주가 이어지는 줄이다.
   - 들여 쓰지 않은 번호 없는 줄에서 멈춘다. 1.5KE의 `Devices for Bipolar Applications` 아래에서 1.·2.가 다시 나오는 경우다.
   - 앞 줄과 20pt 넘게 떨어진 줄에서 멈춘다(바닥글 `Version:`).
   - 앞 줄과 8pt 안쪽으로 붙은 줄은 아래첨자 조각(`BR T T`)으로 보고 건너뛴다. 각주 줄 간격은 약 14pt다.

**청크에 붙어야 할 각주**
- 각주 표시는 그 표의 머리글 행들과 그 행 칸에서 읽는다. 머리글 표시는 모든 행에 해당한다. 형식은 `(1)`, `(Note 1)`, `Note 1`, `*`이다.
- 표 어디에도 표시가 없으면 표 아래 각주 전부가 모든 행에 해당한다. 청커와 같은 규칙이다.
- 표에 표시가 있으면 그 행·머리글이 표시한 번호의 각주만 해당한다. 아무도 가리키지 않는 각주는 `unreferenced`에 기록만 하고 판정에 쓰지 않는다.

**있는지 보는 법**
- 청크의 `\n주:` 뒤 글과 각주 글을 낱말로 비교한다. 낱말은 세 글자 이상 글자 묶음과 숫자다.
- 각주 낱말 중 청크에 있는 비율(`coverage`)이 0.9 이상이면 있음, 0.3 이하면 없음, 그 사이는 판단 보류다.
- 예: `PW = 0.3ms`와 `PW = 30ms`는 0.75라 보류다.

| status | 뜻 |
|---|---|
| `none` | 표 바로 아래에 각주가 없고 그 행·머리글에 표시도 없음 |
| `unmarked` | 표에 각주와 표시가 있지만 이 행·머리글에는 표시가 없음(해당 각주 없음) |
| `attached` | 해당 각주가 모두 청크 `주:`에 있음 |
| `missing` | 해당 각주 중 하나라도 청크에 없음(coverage 0.3 이하) |
| `unclear` | 판단 보류: 표시한 번호의 각주가 그 쪽 표 바로 아래에 없음, coverage가 0.3~0.9, 행을 못 찾음 |

기록하는 것: 각주 번호·coverage·글 앞 90자, 표시(`marks`), 쪽(`page`). `none`·`unclear`이면서 같은 쪽 다른 표 아래에 각주가 있으면 그 표의 첫 행 글자(`notes_under_other_tables`)도 남긴다. 다른 표의 각주를 잘못 나눴는지 보려는 것이다.

## 기존 필드가 그대로인지
| 대조 | 결과 |
|---|---|
| 새 `results.jsonl`에서 `part_check`·`note_check`를 뺀 줄 vs `../chunk_source_check_rows_2026-11-16/results.jsonl` | 123/123 바이트 동일 |
| 위에서 `row_check`도 뺀 줄 vs `../chunk_source_check/results.jsonl` | 123/123 바이트 동일 |
| `summary.json`의 기존 키(`row_check.mutation_control` 포함) vs rows 폴더 | 전부 같음. 더한 키는 `part_check`·`note_check`뿐 |

## 결과 (실제 표본 123개)

### 부품 행 검사: 지난번 `unlocated` 6건
| 문서 | 쪽 | 품번 | 찾은 표·행 | 비교한 칸 | 결과 | 각주 |
|---|---|---|---|---|---|---|
| P6SMB SERIES_Q2209.pdf | 3 | P6SMB100A | 표 0 행 18 | 9 | ok | attached(1·2, 3~5는 표시 없음) |
| 5.0SMDJ SERIES_D2102.pdf | 2 | 5.0SMDJ28A | 표 0 행 10 | 9 | ok | attached(1) |
| 1KSMB10A SERIES_I2102.pdf | 2 | 1KSMB51A | 표 1 행 37 | 8 | ok | unclear(아래) |
| AZ23C2V7 SERIES_D2001.pdf | 2 | AZ23C9V1 | 표 0 행 18 | 10 | ok | attached(표시 없는 표, 1~3 모두) |
| 1SMA5926H SERIES_A2102.pdf | 2 | 1SMA5926H | 표 0 행 5 | 11 | ok | attached(1·2) |
| 1SMA4737 SERIES_P2102.pdf | 2 | 1SMA4757 | 표 0 행 25 | 9 | ok | missing(아래) |

6건 중 6건을 찾았다. `row_mismatch`는 0이고 확인 못 한 칸(`unchecked`)도 0이다. 청크의 값 칸을 모두 PDF 칸과 비교했다(청크당 8~11칸). 이제 행·열 단위로 대조되지 않은 청크는 표본 123개 중 0개다(`row_check` ok 117 + `part_check` ok 6).

### 각주 검사
| status | 전체 | ratings | thermal | electrical |
|---|---|---|---|---|
| `none` | 57 | 37 | 18 | 2 |
| `unmarked` | 18 | 5 | 0 | 13 |
| `attached` | 32 | 0 | 8 | 24 |
| `missing` | **14** | 0 | **13** | 1 |
| `unclear` | 2 | 0 | 0 | 2 |
| 합 | 123 | 42 | 39 | 42 |

- 각주가 해당하는 청크(attached + missing)는 46개다. 그중 thermal은 21개이고, 13개(62%)가 `missing`이다.
- `attached` 32개의 각주 36개는 모두 coverage 1.0이다. `missing`의 빠진 각주는 coverage 0.0(13건)과 0.167(1건)이다. 0.3~0.9 사이에 걸린 각주는 1SMA4757의 각주 2(0.867) 하나뿐이다.
- `none`·`unmarked` 75개 중 `주:`를 담은 청크는 0개다. 표에 없는 각주를 붙인 경우는 없었다.
- `none` 57개 중 26개는 같은 쪽 다른 표 아래에 각주가 있다. 주로 thermal 표 아래가 아니라 그 아래 electrical·ordering 표 아래의 `Notes: 1. Pulse test …`다. 이 26개 청크의 표에는 각주 표시가 없다.
- 손으로 본 것: `none`·`unmarked` 75개 모두 표 아래 첫 줄을 확인했다. 첫 줄은 `● DC to DC converter`·`APPLICATIONS`·`Version:` 같은 각주가 아닌 글이거나 바로 다음 표였다. 놓친 각주 머리는 없었다.

### `missing` 14건 (손 대조: 모두 청크 오류, 검사기 오류 0)
| 문서 | 쪽 | 종류 | 행 | 표·행 | 표시 | 빠진 각주(coverage) |
|---|---|---|---|---|---|---|
| GBJL15J_C2606.pdf | 2 | thermal | Junction-to-ambient thermal resistance | 표 0 행 3 | 없음 | 번호 없음 "Mounted on heat sink with 4" x 6" x 0.25" Al-Plate" (0.0) |
| GBJL15J_C2606.pdf | 2 | thermal | Junction-to-case thermal resistance | 표 0 행 4 | 없음 | 위와 같음 (0.0) |
| RS5D-T SERIES_C2602.pdf | 2 | thermal | Junction-to-ambient thermal resistance | 표 0 행 3 | 없음 | 번호 없음 "Units mounted on PCB (16mm x 16mm Cu pad test board)" (0.0) |
| HS2DFL SERIES_B2103.pdf | 2 | thermal | Junction-to-ambient thermal resistance | 표 0 행 3 | 없음 | 번호 없음 "Units mounted on PCB (5mm x 5mm Cu pad test board)" (0.0) |
| BAT54WH_A2501.pdf | 2 | thermal | Junction-to-ambient thermal resistance(1) | 표 0 행 2 | 1 | 1 "Device mounted on an FR4 Printed-Circuit Board (PCB), single-sided copper, …" (0.0) |
| TSFS3M60H_A2510.pdf | 2 | thermal | Junction-to-ambient thermal resistance | 표 0 행 3 | 없음 | 번호 없음 "Units mounted on PCB (5mm x 5mm Cu pad test board)" (0.0) |
| ES2LDH SERIES_A2102.pdf | 2 | thermal | Junction-to-ambient thermal resistance | 표 0 행 3 | 없음 | 번호 없음 "Units mounted on PCB (16mm x 16mm Cu pad test board)" (0.0) |
| BAW56H_A2412.pdf | 2 | thermal | Junction-to-ambient thermal resistance(1) | 표 0 행 2 | 1 | 1 "Device mounted on an FR4 Printed-Circuit Board (PCB), …" (0.0) |
| 1N4148WSH_A2501.pdf | 2 | thermal | Junction-to-ambient thermal resistance(1) | 표 0 행 2 | 1 | 1 "Device mounted on an FR4 Printed-Circuit Board (PCB), …" (0.0) |
| 1K5SMPC12APH SERIES_B2109.pdf | 2 | thermal | Junction-to-lead thermal resistance | 표 0 행 2 | 없음 | 번호 없음 "Units mounted on PCB (16mm x 16mm Cu pad test board)" (0.0) |
| PU2BB SERIES_A2210.pdf | 2 | thermal | Junction-to-case thermal resistance | 표 0 행 4 | 없음 | 번호 없음 "Units mounted on PCB (10mm x 10mm Cu pad test board)" (0.0) |
| 1PGSMC5348H SERIES_A2102.pdf | 1 | thermal | Junction-to-lead thermal resistance | 표 2 행 2 | 없음 | 번호 없음 "Units mounted on PCB (16mm x 16mm Cu pad test board)" (0.0) |
| 1PGSMB5926H SERIES_A2102.pdf | 1 | thermal | Junction-to-lead thermal resistance | 표 2 행 2 | 없음 | 번호 없음 "Units mounted on PCB (10mm x 10mm Cu pad test board)" (0.0) |
| 1SMA4737 SERIES_P2102.pdf | 2 | electrical | 1SMA4757 | 표 0 행 25 | 1·2·3 | 3 "Zener Voltage (VZ) Measurement. Guarantees the zener voltage when measured at 90 seconds …" (0.167). 2는 0.867 |

**thermal 13건**
- [실측] 13건 모두 PDF에서 표 바로 아래 첫 줄이 `Thermal Performance Note:`로 시작한다. 그 뒤에 각주 글이 같은 줄에 오거나 다음 줄 `1. …`로 온다.
- [실측] 코퍼스에서 이 각주 글은 같은 쪽의 `MECHANICAL DATA` 소제목 글 청크(kind `text`)에 들어 있다. 같은 표의 행 청크(문서당 1~3개)에는 하나도 붙지 않았다.
- BAT54WH·BAW56H·1N4148WSH의 FR4 각주는 1쪽 ABSOLUTE MAXIMUM RATINGS 표의 Power dissipation 행과 그 표의 주석 청크에만 있다.
- [추정] 원인: 청커(`backend/rag/pipeline/chunk.py`)의 `NOTE_HEAD`가 `^notes?`라서 앞말이 붙은 이 머리를 각주 머리로 받지 않는다.
- 같은 머리인데 붙은 표도 있다(HS2DAL·PHAD10J, 행에 머리째 두 번 붙음). Docling이 그 줄을 `footnote`로 분류했을 때만 붙는 것으로 보이나 Docling JSON은 확인하지 않았다.

**1SMA4757**
- [실측] 청크 `주:`는 PDF 각주 1과 각주 2의 첫 항목(`2. Specials Available Include: A. Nominal …`)까지다. 표시 (Note 3)에 해당하는 "Zener Voltage (VZ) Measurement …"는 없다. 각주 2의 `B. Matched sets`도 없어 각주 2가 0.867이다.
- [실측] 같은 쪽 주석 청크(kind `note`)에는 1·3·4번 앞 번호와 `B.`가 빠진 채(`Tolerance …`, `2. Specials …`, `A. Nominal …`, `Matched sets`, `Zener Voltage (Vz) …`) 들어 있다.
- [추정] 원인: 청커 `note_map`은 번호가 없는 줄을 묶음 안 순서로 번호를 매긴다. 그래서 3번째 줄 `A. Nominal …`이 각주 3으로 붙은 것으로 보인다. 붙은 주석 길이는 239자라 `NOTE_MAX`(400) 때문은 아니다.

### `unclear` 2건 (판단 보류, 일치로 세지 않음)
| 문서 | 쪽 | 행 | 표시 | 이유 | 손 대조 |
|---|---|---|---|---|---|
| TUAU10DH SERIES_A2111.pdf | 2 | Reverse current @ rated VR(2) / TJ = 125°C (표 1 행 19) | 2 | 2쪽 표 아래에는 각주 1만 있고 쪽이 끝남(`marks_without_note: ["2"]`) | 3쪽 맨 위 줄이 "2. Pulse test with PW = 30ms"이고 청크도 이것을 담았다. 실제로는 붙어 있다. 검사기가 같은 쪽만 보는 한계다. |
| 1KSMB10A SERIES_I2102.pdf | 2 | 1KSMB51A (표 1 행 37) | 1(머리글 `(Note 1)`) | 2쪽 표 아래에 각주 없음(표가 3쪽으로 이어짐) | 3쪽의 이어진 표 아래에 "Notes: 1. VBR measure after IT applied for 30ms …"가 있다. 이 청크와 같은 표 행 청크 42개 모두에 `주:`가 없다. 각주 1이 빠진 것으로 보이지만 규칙(같은 쪽) 밖이라 `missing`으로 세지 않았다. |

## 검사기가 되는지: 변이 시험

### 합성 표(`tests/evals/test_chunk_source_check.py`, 17개 통과 = 기존 8 + 새 9)
- 부품 행 표: P6SMB 3쪽 모양(제목 행, 두 줄 머리글, (Note 1)·(Note 2), 품번 4개).
- 각주 줄: P6SMB·BAW56H·HS2DFL·BAV19W·AZ23C·1.5KE의 실제 줄 위치를 옮겨 적었다.

| 변이 | 개수 | 쪽 검사가 잡음 | 새 검사가 잡음 |
|---|---|---|---|
| 부품 행: 다른 품번 행의 같은 열 값 | 48 | 0 | **48** (`row_mismatch`) |
| 부품 행: 같은 행 다른 열 값 | 80 | 0 | **80** |
| 부품 행: 출처 진단(Min 95→90.0, Min↔Max) | 2 | - | 2 (`다른 행 같은 열`, `같은 행 다른 열`) |
| 각주 글 전부 지움(부품 행 4, ELEC 6, THERM 2) | 12 | - | **12** (`missing`) |
| 각주 2만 지움(부품 행) | 4 | - | **4** (`missing`) |
| 각주 1·2 글 맞바꿈(ELEC, `0.3ms`↔`30ms`) | 6 | - | 6 모두 `attached` 아님(`unclear`, 낱말이 겹쳐 `missing`까지는 안 감) |
| 깨끗한 청크(부품 행 4, ELEC 7, THERM 1) | 12 | 막음 0 | 막음 0(`attached` 11, 표시 없는 행 `unmarked` 1) |
| 표시는 있는데 표 아래 각주 없음 / 표시한 번호가 없음 | 2 | - | 2 모두 `unclear` |

- 모르는 품번은 `unlocated`이고, PDF 머리글에 없는 열 이름은 `unchecked`로 남아 일치로 세지 않는다.
- 판정을 일부러 망가뜨려도 확인했다. 부품 행 불일치를 항상 `ok`로, 각주 판정을 항상 `attached`로 바꾸면 새 시험 5개가 실패한다(시험이 비어 있지 않음).

### 실제 표본(`summary.json`의 `note_check.mutation_control`)
| 변이 | 시도 | 쪽 검사가 잡음 | 새 검사가 잡음 |
|---|---|---|---|
| 부품 행 `ok` 6개: 다른 품번 행의 같은 열 값(바꿀 수 있는 것 전부) | 1,265 | 0 | **1,265** |
| 부품 행 `ok` 6개: 같은 행 다른 열 값(전부) | 422 | 0 | **422** |
| 각주 `attached` 32개: `주:` 글 지움 | 32 | - | **32** (`missing`) |

## 사전 등록 기대와 비교
| 기대 | 결과 |
|---|---|
| (1) 지난 `unlocated` 6건 중 5건 이상을 부품 행 표로 찾고 `row_mismatch` 0 | 6/6 찾음, `row_mismatch` 0 (맞음) |
| (2) 각주가 있는 표의 청크가 있고, 그중 thermal에서 `missing`이 다수 [추정] | 각주가 해당하는 청크 46개 중 thermal 21개, 그중 `missing` 13(62%) (맞는 방향). 다만 지난 기록의 "216표 중 THERMAL 122"와 같은 모집단을 센 것은 아니다. 이번 13건의 머리는 모두 `Thermal Performance Note:`였다. |
| (3) 합성 변이 탐지 100%, 깨끗한 청크 오탐 0 | 부품 행 128/128, 각주 지움 16/16, 오탐 0 (맞음) |

## 남은 한계
1. **같은 쪽만 본다.** 다음 쪽으로 넘어간 각주(TUAU10DH 각주 2)나 쪽을 넘는 표의 각주(1KSMB10A)는 `unclear`다. 위 2건은 손으로 봤다.
2. **표 바로 아래 첫 줄이 각주 머리여야 한다.** 표와 각주 사이에 다른 글이 끼면 `none`이 된다. 표본 75개(`none`·`unmarked`)의 첫 줄은 손으로 봤지만, 표본 밖은 모른다.
3. **각주 표시는 괄호형(`(1)`, `(Note 1)`)·`Note 1`·`*`만 읽는다.** 괄호 없는 위첨자 숫자는 못 읽는다. 표본 118쪽 표 안의 작은 글씨 숫자 215개를 따로 셌다. 208개는 괄호 안 표시, 6개는 `I²t`·`A²s` 단위, 1개는 `D2PAK` 글자였고, 괄호 없는 위첨자 각주 표시는 0개였다. `*` 표시는 표본에 없었다.
4. **"표에 표시가 없으면 각주 전부가 모든 행에 해당"은 규칙 선택이다(청커와 같음).** AZ23C처럼 가격·문의 안내 각주도 해당으로 본다.
5. **낱말 비율(0.9/0.3)은 글 존재만 본다.**
   - 다른 각주 글로 바뀐 경우(`0.3ms`↔`30ms`)는 `missing`이 아니라 `unclear`로 남는다.
   - 숫자 하나만 바뀐 각주는 놓칠 수 있다(낱말 10개 중 1개면 0.9).
   - 각주 글 자체의 정확성은 검증하지 않는다.
6. **부품 행 검사의 한계.**
   - 품번 칸 이름(Device·Part number)은 비교하지 않는다.
   - 두 품번 행의 칸 값이 같으면 바꿔도 오류로 셀 수 없다. 예: Test current가 모두 1.0이라 합성 변이에서 그 열은 변이가 생기지 않는다.
   - 머리글이 앞 쪽에만 있는 이어진 표는 `unlocated`가 된다(이번 표본은 0건).
7. **`page_tables`·`page_notes`(pdfplumber 어댑터)는 단위 시험이 없다.** 원본 PDF가 저장소 밖이다. 대신 실제 표본 실행, 실제 표본 변이(부품 행 1,687건, 각주 지움 32건), `missing`·`unclear` 16건과 `none`·`unmarked` 75건의 손 대조로 확인했다.
8. **청커 원인 두 가지(앞말 붙은 머리, 번호 없는 각주의 순서 번호)는 코드와 코퍼스를 읽고 추정한 것이다.** 청커를 다시 돌려 확인하지 않았다. 코퍼스는 고치지 않았다(재처리는 동결 전 범위 밖).
9. **표본 123개는 전체 표 행의 약 0.3%다.** thermal `missing` 13/39를 전체 비율로 일반화하지 않는다. PDF 파일 sha256을 `data/manifest.jsonl`과 대조하지 않은 것은 지난번과 같다.

## 파일
- `results.jsonl`: 청크별 기존 필드 + `row_check` + `part_check` + `note_check`. 새 키는 기존 키 뒤에만 더했다.
  - `part_check`: status, table, row, checked, unchecked, mismatch.
  - `note_check`: status, reason, marks, notes[번호·coverage·글], unreferenced, marks_without_note, page, notes_under_other_tables.
- `summary.json`: 기존 집계 + `part_check`(해당 6, ok·row_mismatch·unlocated) + `note_check`(status별, 표 종류별, 이유별, `mutation_control`)
- 도구: `scripts/eval/chunk_source_check.py` (`--notes`), 시험: `tests/evals/test_chunk_source_check.py`
