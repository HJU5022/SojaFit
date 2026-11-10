# corpus

## 역할

- baseline_cases.json의 t3_smoke는 정상/공격 2작업 전용 승인 범위다. 전체110회 execution_enabled=false는 유지하며 별도 해시·사전등록·정확한 커밋/승인 없이는 유료 실행할 수 없다.
- 이 폴더: 코퍼스 원본 문서를 출처별로 둡니다. 지금은 TSC 다이오드 데이터시트 표본 3건뿐이며, 전체 1,360건은 저장소에 포함하지 않습니다. 원본은 고치지 않습니다.
- 넣는 것: `tsc/`(Taiwan Semiconductor 다이오드 데이터시트 원본 PDF 표본).
- 넣지 않는 것: 파싱 결과와 목록(문서 목록은 `data/manifest.jsonl`, 청크·파싱 결과는 저장소 밖 작업 자료, 키 없는 데모용 42문서 청크만 `data/demo/snapshot/`), 재배포를 금지하는 제조사(TI, Diodes, Vishay, ST, Nexperia, PANJIT)의 데이터시트, TSC PDF 전체.
- 담당: 검색·데이터

## 파일
- `tsc/` — 제조사 PDF 원본 표본 3건: `BZT52C2V4-SERIES_G1804.pdf`, `1N4148-SERIES_K2301.pdf`, `1N5817-SERIES_H2104.pdf`. 출처·개정판·해시는 [manifest](../manifest.jsonl)에 기록합니다. manifest에는 원래 파일 이름(공백 포함)이 `source_url` 끝에 있고 해시가 같습니다
- `public/` — KiCad 문서·Wikipedia·SparkFun Learn 등 공개 라이선스 문서 자리(SPEC 6절). 아직 받지 않아 `.gitkeep`뿐입니다
- `injection_tests/` — 자체 작성 합성 JSON 7건(2026-11-09~10, STH). 실제 비밀값·제조사 원문이 아니며 공용 `data/manifest.jsonl`·G3 코퍼스 집계·공유 DB 적재에서 제외합니다. 명시적으로 선택한 격리 시험 DB에서만 시험용 사본을 적재합니다. 이 자료가 있다는 것이 방어 성공을 뜻하지 않습니다. 담당은 평가·문서
  - `baseline_cases.json` — T1~T7 정상·공격 짝, 합성 회로·공개 사양·보호 사실, 110회 채점 기준과 공식 단가 스냅샷·예산 가정. 유료 실행은 비활성. 정답·채점 필드는 모델 입력에서 제외합니다
  - `instruction_override.json`(상위 지시 사칭), `source_exfiltration.json`(원문·링크 유출), `foreign_memory.json`(타 사용자 사례 권한 사칭) — 각 문서 `purpose=injection_test`. `evals/runners/run_trust_boundary.py`가 메모리 검색 결과로만 주입합니다. 배포 HTTP 공격 시험은 별도입니다
  - `judgement_bundle_v1.json` — 로컬 BM25 검색·MCP 사양·판정용 정상 1건/공격 3건. `run_judgement_bundle`의 plan/load/preflight/simulate 입력이며 실제 모델 시험은 전건 not_run입니다. load/preflight/simulate는 사양 표(`part_specifications`)와 MCP 사양 도구를 쓰므로 사양 표 제거(ADR 0016) 뒤 현재 코드에서는 돌지 않습니다
  - `claim_consistency_cases_v1.json` — `judgement_bundle_v1.json`(불충족 대조군)을 hash로 참조하는 거짓 인용 주장(C1)·설명/판정표 충돌(C2) 2건. 유출 표식 없이 의미적 조작을 보며 정상/위험 예시와 수동 판정표를 포함합니다
  - `input_surfaces_v1.json` — 다섯 입력 위치 정상/공격 10건. 이름/소속 4건은 미확정이고 나머지는 고정 청크와 실제 파서·문서 에이전트 컴포넌트 시험용입니다. baseline hash를 고정합니다

## 만들지 않는 것
- `infineon/` — Infineon 다이오드 데이터시트. 3차 범위 밖(확장 후보)이라 수집하지 않습니다(SPEC 6절).

## 이용 조건
- Taiwan Semiconductor 사이트 약관은 정보·비상업 목적에 한해, 고치지 않고 저작권 고지를 유지하고 출처를 밝히는 조건으로 복제·배포를 허용합니다. PDF는 고치지 않고 고지·출처와 함께 둡니다. Infineon 약관도 같은 취지지만 3차 범위 밖이라 수집하지 않았습니다(SPEC 6절).
- 공개 문서를 받게 되면 원래 라이선스(CC BY-SA 4.0 등)를 따르고 출처를 적습니다.

## 수집과 검색 반영 상태

저장소에는 1,360건의 v1 문서 목록(청크 수 합계 52,244), PDF 표본 3건, 키 없는 데모용 스냅샷(42문서·청크 1,556개, `data/demo/snapshot/`)만 있습니다. 최신 `main`의 청킹 코드는 `tsc-v4h-2026-11-08`이고, 2026-11-08 작업 기록에는 저장소 밖 전체 입력으로 카드 51,967개를 생성해 별도 로컬 DB에 적재하고 검색 103질의를 측정한 결과가 있습니다. 다만 전체 PDF·Docling JSON·v4h 전체 청크·DB는 저장소에 없으므로 새 clone에서 그 실행을 재현할 수 있다는 뜻은 아닙니다. 현재 서비스 검색 코드는 `voyage-4-large` 1024차원 dense 검색과 BM25를 RRF로 합치고 `rerank-3`로 재정렬합니다. 실제 사용 코퍼스 버전은 실행별 입력 수·DB 행 수·manifest·`chunker_version`과 결과 해시로 확인합니다.
같은 계열명이나 전압이라는 이유로 원래 회로 부품의 데이터시트라고 확정하지 않습니다. 제조사·정확한 주문 품번·패키지를 대조해야 합니다.
