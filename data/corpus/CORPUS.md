# corpus

## 역할
- 이 폴더: 코퍼스 원본 문서를 출처별로 둔다. TSC 다이오드 데이터시트 표본 3건과 인젝션 시험용 합성 자료가 있다. 전체 1,360건은 저장소에 없다. 원본은 고치지 않는다.
- 넣는 것: `tsc/`(Taiwan Semiconductor 다이오드 데이터시트 원본 PDF 표본), `injection_tests/`(자체 작성 합성 JSON).
- 넣지 않는 것: 파싱 결과와 목록(문서 목록은 `data/manifest.jsonl`, 청크·파싱 결과는 저장소 밖 작업 자료, 키 없는 데모용 청크는 `data/demo/snapshot/`), 재배포를 금지하는 제조사(TI, Diodes, Vishay, ST, Nexperia, PANJIT)의 데이터시트, TSC PDF 전체.
- 담당: 검색·데이터 (`injection_tests/`는 평가·문서)
- 코퍼스 문서·쪽·청크 수: [DATA.md](../DATA.md) "코퍼스 수치".

## 파일

| 파일·폴더 | 유형 | 설명 |
|---|---|---|
| `CORPUS.md` | 폴더 설명 | 이 문서 |
| `tsc/` | 데이터시트 원본 | 제조사 PDF 표본 3건: `BZT52C2V4-SERIES_G1804.pdf`, `1N4148-SERIES_K2301.pdf`, `1N5817-SERIES_H2104.pdf`. 출처·개정판·해시는 [manifest](../manifest.jsonl). manifest에는 원래 파일 이름(공백 포함)이 `source_url` 끝에 있고 해시가 같음 |
| `public/` | 자리 | KiCad 문서·Wikipedia·SparkFun Learn 등 공개 라이선스 문서 자리(SPEC 6절). 받은 문서 없음, `.gitkeep`뿐 |
| `injection_tests/` | 합성 시험 자료 | 자체 작성 합성 JSON 7건. 실제 비밀값·제조사 원문이 아니며 공용 `data/manifest.jsonl`·G3 코퍼스 집계·공유 DB 적재에서 제외. 명시적으로 선택한 격리 시험 DB에만 시험용 사본을 적재 |
| `injection_tests/baseline_cases.json` | 합성 시험 자료 | T1~T7 정상·공격 짝, 합성 회로·공개 사양·보호 사실, 110회 채점 기준, 공식 단가 스냅샷, 예산 가정. 전체 110회 `execution_enabled=false`, 범위별 `t3_smoke`·`exposure_pilot`·`remaining_smoke`·`t7_smoke`는 `true`. 정답·채점 필드는 모델 입력에서 제외 |
| `injection_tests/instruction_override.json` | 합성 시험 자료 | 상위 지시 사칭 문서. `purpose=injection_test`. `evals/runners/run_trust_boundary.py`가 메모리 검색 결과로만 주입 |
| `injection_tests/source_exfiltration.json` | 합성 시험 자료 | 원문·링크 유출 시도 문서. 같은 실행기가 사용 |
| `injection_tests/foreign_memory.json` | 합성 시험 자료 | 타 사용자 사례 권한 사칭 문서. 같은 실행기가 사용 |
| `injection_tests/judgement_bundle_v1.json` | 합성 시험 자료 | 로컬 BM25 검색·MCP 사양·판정용 정상 1건·공격 3건. `run_judgement_bundle.py`의 `plan`·`load`·`preflight`·`simulate` 입력. `load`·`preflight`·`simulate`는 제거된 사양 표(`part_specifications`, ADR 0016)와 MCP 사양 도구를 써서 현재 코드에서 돌지 않음 |
| `injection_tests/claim_consistency_cases_v1.json` | 합성 시험 자료 | `judgement_bundle_v1.json`(불충족 대조군)을 hash로 참조하는 거짓 인용 주장(C1)·설명/판정표 충돌(C2) 2건. 정상/위험 예시와 수동 판정표 포함. `run_claim_consistency.py` 입력 |
| `injection_tests/input_surfaces_v1.json` | 합성 시험 자료 | 다섯 입력 위치 정상/공격 10건. 이름/소속 4건은 미확정, 나머지는 고정 청크와 실제 파서·문서 에이전트 컴포넌트 시험용. baseline hash를 고정. `run_input_surfaces.py` 입력 |

이 폴더의 합성 자료가 있다는 사실은 방어 성공을 뜻하지 않는다. 실측 결과는 [injection-results.md](../../docs/research/injection-results.md).

## 만들지 않는 것
- `infineon/` — Infineon 다이오드 데이터시트. 3차 범위 밖(확장 후보)이라 수집하지 않는다(SPEC 6절).

## 이용 조건
- Taiwan Semiconductor 사이트 약관은 정보·비상업 목적에 한해, 고치지 않고 저작권 고지를 유지하고 출처를 밝히는 조건으로 복제·배포를 허용한다. PDF는 고치지 않고 고지·출처와 함께 둔다. Infineon 약관도 같은 취지지만 3차 범위 밖이라 수집하지 않는다(SPEC 6절).
- 공개 문서를 받으면 원래 라이선스(CC BY-SA 4.0 등)를 따르고 출처를 적는다.

## 한계
- 전체 PDF·Docling JSON·v4h 전체 청크·DB는 저장소에 없다. 새 clone에서 전체 청킹·적재를 재현할 수 없다.
- 같은 계열명이나 전압이라는 이유로 원래 회로 부품의 데이터시트라고 확정하지 않는다. 제조사·정확한 주문 품번·패키지를 대조해야 한다.
