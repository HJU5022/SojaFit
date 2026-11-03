# corpus

## 역할
- 이 폴더: 코퍼스 원본 문서를 출처별로 둡니다. 지금은 TSC 다이오드 데이터시트 표본 3건뿐이며, 전체 1,360건은 저장소 밖 `../corpus/tsc/pdf/`에 있습니다. 원본은 고치지 않습니다.
- 넣는 것: `tsc/`(Taiwan Semiconductor 다이오드 데이터시트 원본 PDF 표본).
- 넣지 않는 것: 파싱 결과와 목록(문서 목록은 `data/manifest.jsonl`, 청크·파싱 결과는 저장소 밖 `../corpus/tsc/`), 재배포를 금지하는 제조사(TI, Diodes, Vishay, ST, Nexperia, PANJIT)의 데이터시트, TSC PDF 전체(저장소 밖 `../corpus/tsc/pdf/`).
- 담당: 검색·데이터

## 파일
- `tsc/` — 제조사 PDF 원본 표본 3건: `BZT52C2V4-SERIES_G1804.pdf`, `1N4148-SERIES_K2301.pdf`, `1N5817-SERIES_H2104.pdf`. 출처·개정판·해시는 [manifest](../manifest.jsonl)에 기록합니다. manifest에는 원래 파일 이름(공백 포함)이 `source_url` 끝에 있고 해시가 같습니다
- `public/` — KiCad 문서·Wikipedia·SparkFun Learn 등 공개 라이선스 문서 자리(SPEC 6절). 아직 받지 않아 `.gitkeep`뿐입니다
- `injection_tests/` — 간접 인젝션 시험 문서 3건 이상 자리. 만들면 manifest의 용도 열로 코퍼스 집계와 구분합니다. 담당은 평가·문서이며 지금은 `.gitkeep`뿐입니다

## 만들지 않는 것
- `infineon/` — Infineon 다이오드 데이터시트. 3차 범위 밖(확장 후보)이라 수집하지 않습니다(SPEC 6절).

## 이용 조건
- Taiwan Semiconductor 사이트 약관은 정보·비상업 목적에 한해, 고치지 않고 저작권 고지를 유지하고 출처를 밝히는 조건으로 복제·배포를 허용합니다. PDF는 고치지 않고 고지·출처와 함께 둡니다. Infineon 약관도 같은 취지지만 3차 범위 밖이라 수집하지 않았습니다(SPEC 6절).
- 공개 문서를 받게 되면 원래 라이선스(CC BY-SA 4.0 등)를 따르고 출처를 적습니다.

## 수집과 검색 반영 상태

TSC 데이터시트 1,360건은 Docling 파싱을 마쳤고(결과는 저장소 밖 `../corpus/tsc/`), 청킹도 로컬에서 마쳤습니다. 카드 52,244장은 로컬 DB에 넣고 `text-embedding-3-small` 임베딩을 붙여 하이브리드 검색(`backend/rag/retrieve.py`)에 씁니다(ADR 0005 로컬 실측). 이 폴더의 `tsc/` 3건은 표본입니다.
같은 계열명이나 전압이라는 이유로 원래 회로 부품의 데이터시트라고 확정하지 않습니다. 제조사·정확한 주문 품번·패키지를 대조해야 합니다.
