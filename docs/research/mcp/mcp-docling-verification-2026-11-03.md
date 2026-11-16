# 저장소 PDF 3건의 Docling·pdfplumber 표 숫자 대조

- 상태: 이력 (2026-11-03 측정 기록. 재실행하지 않았다)
- 기준일: 2026-11-03
- 정본 여부: 정본(저장소 TSC 표본 3건의 표 파싱 점검 결과). 원시 결과는 저장소에 없다(한계 1)
- 관련 문서: [MCP 서버 도구 6종](mcp-tool-implementation-plan.md), [DB 없는 저장소 표본 점검](mcp-offline-verification-2026-11-03.md), [RAG 안내](../../../backend/rag/RAG.md), [RAG 작업서](../../specs/rag-pipeline.md), [사전 등록](../../../evals/guides/preregister.md)

## 1. 질문과 결론

질문: 저장소 TSC PDF 3건에서 Docling이 읽은 표 숫자가 pdfplumber 텍스트와 일치하는가.

| 항목 | 값 | 근거 |
|---|---|---|
| 파싱 성공 | 3/3 (쪽 수 5·6·7 = manifest와 일치) | 아래 3.1, `data/manifest.jsonl` |
| 문서당 Docling 표 | 쪽마다 1개 이상(5·6·7개, 합계 18) | 3.1 |
| Docling 숫자 → pdfplumber 같은 쪽 텍스트 | 515/515 | 3.1 |
| PDF 표 영역 숫자 → Docling | 515개 중 누락 0 | 3.1 |
| 사전 기대(3건 파싱 성공, 쪽 수 일치, 문서당 표 1개 이상, 숫자 일치율 0.80~1.00) | 충족 | 3.1 |
| 한계 | 숫자 누락 점검용 보조 지표. 표 전체 누락, 우연한 같은 숫자 일치, 단위·시험 조건·품번과 숫자의 연결 오류는 검증하지 않음 | |

## 2. 방법과 환경

| 항목 | 값 |
|---|---|
| 대상 | `data/corpus/tsc/`의 1N4148 K2301, 1N5817 H2104, BZT52C2V4 G1804 데이터시트 |
| 코드 | `backend/rag/pipeline/parse.py`의 `run`·`recall`. Docling은 OCR을 끄고 표 구조를 켬 |
| 환경 | Windows, Python 3.12.10, Docling 2.145.0, pdfplumber 0.11.10, PyTorch 2.15.0, `torch.cuda.is_available()`=false |
| 시간 제한 | Windows 기본 파서에는 파일별 SIGALRM 제한이 없어 상위 프로세스에서 PDF별 600초 제한 |
| 호출 | DB·LLM·검색 API 호출 없음 |
| 원본 보존 | 3건의 SHA-256과 바이트 수가 `data/manifest.jsonl` 기록과 일치한다 [실측] 2026-11-12 재계산 |
| 의존성 | `pyproject.toml`의 `docling>=2.145`, `pdfplumber>=0.11.10` |

숫자 대조는 두 방향이다. (1) Docling 표 셀의 숫자가 같은 쪽 pdfplumber 텍스트 어딘가에 있는지, (2) Docling이 찾은 표 영역 안에서 pdfplumber로 추출한 숫자가 Docling 표에도 있는지.

## 3. 결과

### 3.1 문서별

| PDF | 쪽 | Docling 표 | (1) Docling 숫자 → pdfplumber | (2) PDF 표 영역 숫자 → Docling | 파싱·대조 시간 |
|---|---:|---:|---:|---:|---:|
| 1N4148-SERIES_K2301 | 5 | 5 | 81/81 | 81개 중 누락 0 | 53.02초 |
| 1N5817-SERIES_H2104 | 6 | 6 | 49/49 | 49개 중 누락 0 | 17.39초 |
| BZT52C2V4-SERIES_G1804 | 7 | 7 | 385/385 | 385개 중 누락 0 | 32.29초 |
| 합계 | 18 | 18 | 515/515 | 515개 중 누락 0 | |

시간은 기존 parser 로그의 값이다. 첫 문서의 모델 초기화와 운영 환경 차이가 있어 벤치마크가 아니다.

### 3.2 대표 정격 행의 좌표 대조

각 PDF의 첫 표에서 대표 행 1개의 Docling 셀과 같은 행의 pdfplumber 좌표 영역 텍스트를 비교했다.

| 문서 | 쪽·표 | Docling 행 | pdfplumber 동일 영역 |
|---|---|---|---|
| 1N4148 K2301 | 1쪽·표 1 | VRRM / 100 / V | V와 아래첨자 RRM, 100 V |
| 1N5817 H2104 | 1쪽·표 1 | VRRM / 20 - 40 / V | V와 아래첨자 RRM, 20 - 40 V |
| BZT52C2V4 G1804 | 1쪽·표 1 | VF at IF=10mA / 1 / V | VF, IF=10mA, 1 V. 아래첨자는 분리 추출 |

선택한 3행의 숫자·단위·문자 출현 확인이다. 모든 행의 품번 대응, 최대·최소 의미, 시험 조건, 대체 가능 여부는 검증하지 않았다.

### 3.3 그 밖의 관찰

- 같은 날 pypdf 점검에서는 manifest 문서명 전체의 `SERIES` 문자열이 세 PDF 텍스트에서 추출되지 않았다([DB 없는 저장소 표본 점검](mcp-offline-verification-2026-11-03.md)). 이름 전체의 단순 문자열 일치만으로 PDF를 거부하면 안 된다.
- 의존성 설치 뒤 파서·MCP 회귀 시험 23개 통과(당시 기록).

## 4. 결정에 미치는 영향

정해진 것: 저장소 표본 3건은 Docling 표 파싱과 숫자 대조 기준을 통과했다. 정해지지 않은 것: 신규 PDF의 서비스 검증·적재 계약(출처, 크기·시간 제한, 실패 격리, 결과 반영)은 MCP 도구에 구현되어 있지 않다([MCP 서버 도구 6종](mcp-tool-implementation-plan.md) 3절).

## 5. 한계

1. 입력 사본, Docling JSON, witness, recall, 로그, 결과 요약 JSON은 저장소 밖 작업 폴더에 있었고 저장소에 없다. 표의 숫자는 재현하지 않았다.
2. 요청 품번·개정판이 표지와 해당 표 행에 연결되는지 검증하지 않았다.
3. 표 병합 셀, 단위, 최솟값·최댓값, 온도·전류 등 시험 조건과 행의 연결을 검증하지 않았다.
4. 재실행 조건: `backend/rag/pipeline/parse.py` 사용법과 uv `ingest` 그룹은 [RAG 안내](../../../backend/rag/RAG.md)와 [RAG 작업서](../../specs/rag-pipeline.md)를 따른다. 모델·패키지가 캐시에 없으면 내려받기가 필요하다. Windows에서는 파일별 시간 제한을 상위 프로세스로 걸어야 한다.
