# corpus

## 역할
- 이 폴더: 코퍼스 원본 문서를 출처별로 둡니다. 원본은 고치지 않습니다.
- 넣는 것: `tsc/`(Taiwan Semiconductor 다이오드 데이터시트), `infineon/`(Infineon 다이오드 데이터시트), `public/`(KiCad 문서·Wikipedia·SparkFun 등 공개 라이선스 문서), `injection_tests/`(간접 인젝션 시험 문서 3건 이상. manifest의 용도 열로 코퍼스 집계와 구분).
- 넣지 않는 것: 파싱 결과와 목록(`data/manifest.jsonl`, `chunks.jsonl`, `params.jsonl`), 재배포를 금지하는 제조사(TI, Diodes, Vishay, ST, Nexperia, PANJIT)의 데이터시트.
- 담당: 검색·데이터 (`injection_tests/`는 평가·문서)

## 이용 조건
- Taiwan Semiconductor와 Infineon 사이트 약관은 정보·비상업 목적에 한해, 고치지 않고 저작권 고지를 유지하고 출처를 밝히는 조건으로 복제·배포를 허용합니다. PDF는 고치지 않고 고지·출처와 함께 둡니다.
- 공개 문서는 원래 라이선스(CC BY-SA 4.0 등)를 따르고 출처를 적습니다.

## 파일
- `CORPUS.md` — 이 폴더 설명
- `tsc/` — 제조사 PDF 원본 3건: BZT52C2V4-SERIES_G1804.pdf, 1N4148-SERIES_K2301.pdf, 1N5817-SERIES_H2104.pdf. 출처·개정판·해시는 [manifest](../manifest.jsonl)에 기록한다.

## 수집과 검색 반영 상태

현재 PDF는 다운로드·문서 검사 단계다. 파싱·청킹·검색 색인·평가셋 반영은 아직 하지 않았다.
같은 계열명이나 전압이라는 이유로 원래 회로 부품의 데이터시트라고 확정하지 않는다. 제조사·정확한 주문 품번·패키지를 대조해야 한다.
