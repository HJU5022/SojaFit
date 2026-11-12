# 문제와 시장 근거: 사실·가설 구분, 페르소나, 고객 여정 맵, 대체재 비교 설계

- 최초 작성일: 2026-11-03
- 현행 상태 확인일: 2026-11-12 (`OSC`, 기준 `758cbcc`). 1~3절과 5~7절의 11-03 조사·설계·실측은 당시 기록이며 현재 성능을 뜻하지 않는다. 현재 승인 흐름은 4절, v3 비교 정본 반영 제안은 7-1 앞 주석을 따른다.
- 기준 문서: [docs/TOPIC.md](../TOPIC.md), [SPEC.md](../../SPEC.md), [EVAL_REPORT.md](../../EVAL_REPORT.md), [docs/reference/evaluation-prep.md](../reference/evaluation-prep.md)
- 목적: 평가 1축(문제와 시장 근거, 15점)의 다섯 항목(채용 공고 50건 분석, 사용자·지불 주체 사실/가설 구분, 반복 문서 업무·페르소나·고객 여정 맵, 범용 챗봇과 동일 질문 5개 비교, 외부 검토 1명 기록)에 대해 저장소 안팎의 확인 사실과 가설, 남은 조치를 구분해 기록한다.

---

## 1. 목표 직무·산업 채용 공고 분석과 역량 연결

### 1-1. 현재 시장·직무 근거

현재 평가와 발표에서는 [전자부품·제조 기술문서 인접 채용 공고 조사서](sojafit-domain-jobs-2026-11-12.md)에서 선정한 **50개 역할·후보 그룹**을 사용한다. 공고별 URL, 업무·요건과 확인 한계는 조사서와 아래 50개 링크 표에서 확인할 수 있다. 사용자는 2026-11-12에 선정된 50건을 수동 검증하고 모두 이상 없다고 확인했다.

조사서의 원자료 확인 기준은 2026-11-12 KST다. 전자부품 직접 분야와 제조·기술문서 등 인접 분야, 마감된 공고가 포함되고, 동일 역할의 여러 게시처는 한 그룹으로 묶은 경우가 있다. 따라서 이 50개를 모두 전자부품 RAG 개발 공고로 표현하거나 시장 규모·고객 수로 해석하지 않는다. 공고는 이후 변경·마감되거나 접근이 제한될 수 있다.

과거 2026-10-29의 237건 집계는 당시 제출한 [주제서](../TOPIC.md)에 남아 있는 이력이다. 개별 원자료 사본은 [`evidence/`](evidence/EVIDENCE.md)에 있으나 현재 평가·발표의 채용 근거로 사용하지 않으며, 아래 50개와 같은 모집단이라고 보거나 합산하지 않는다.

### 1-2. 50개 채용 역할 분석: 반복 업무와 요구 역량 (2026-11-12 자료)

**분석 범위:** 아래에 열거한 50개 역할·후보 그룹을 사용했다. 도메인·AI 개발 28개(001~028), 산업 SW·임베디드 4개(032·034·036·038), 회로·부품·하드웨어 13개(039·040·043~047·050·052·055·057~059), 기술지원·기술영업 4개(060·064~066), 부품 구매·공급망 1개(070)다. SojaFit의 기술문서 검색·에이전트뿐 아니라 부품 선정 업무와 접하는 역할을 포함한다. 서로 다른 게시처의 같은 역할은 조사서에서 한 그룹으로 묶었고, 일부는 접근·상세 확인에 한계가 있다. 공고 50건의 모집단은 과거 주제서의 237건 조사와 다르다. 2026-11-12 사용자가 선정된 50건을 수동으로 검증하고 모두 이상 없다고 확인했다. 아래 해석은 각 공고의 업무 요약을 바탕으로 했다.

| 반복 업무 | 확인되는 요구 역량·도구 | 조사서 예시 | SojaFit과의 연결 |
|---|---|---|---|
| 기술문서·도면·데이터시트·BOM을 읽고 구조화 | PDF·문서 파싱, OCR, 데이터 구조화, 원문 위치·단위·조건 보존 | [001](sojafit-domain-jobs-2026-11-12.md#job-001), [004](sojafit-domain-jobs-2026-11-12.md#job-004), [018](sojafit-domain-jobs-2026-11-12.md#job-018), [026](sojafit-domain-jobs-2026-11-12.md#job-026) | 데이터시트 표·조건·출처를 검색 가능한 근거로 다룬다. |
| 문서 근거 검색과 평가 | 청킹·임베딩, 키워드·벡터 검색, 리랭킹, 평가셋과 검색 품질 측정 | [007](sojafit-domain-jobs-2026-11-12.md#job-007), [017](sojafit-domain-jobs-2026-11-12.md#job-017), [018](sojafit-domain-jobs-2026-11-12.md#job-018), [025](sojafit-domain-jobs-2026-11-12.md#job-025) | 문서 검색·리랭킹과 평가셋을 연결한다. 개별 채용 공고와 서비스 성능은 별개의 근거다. |
| 에이전트·API·서비스 구현 | Python, Tool Calling, LangGraph, FastAPI, DB·비동기 처리, 상태 관리와 테스트 | [002](sojafit-domain-jobs-2026-11-12.md#job-002), [003](sojafit-domain-jobs-2026-11-12.md#job-003), [005](sojafit-domain-jobs-2026-11-12.md#job-005), [011](sojafit-domain-jobs-2026-11-12.md#job-011) | 에이전트 흐름과 API를 구성한다. 공고에 나온 모든 도구를 서비스가 구현한 것은 아니다. |
| 회로·부품 검토와 보드 검증 | 회로·PCB 이해, 부품 선정·BOM, Bring-up, 시험·신뢰성 및 변경 관리 | [040](sojafit-domain-jobs-2026-11-12.md#job-040), [044](sojafit-domain-jobs-2026-11-12.md#job-044), [045](sojafit-domain-jobs-2026-11-12.md#job-045), [050](sojafit-domain-jobs-2026-11-12.md#job-050) | 회로 역할을 바탕으로 대체 부품을 검토하는 문제와 맞닿는다. 실제 보드 시험이나 동작을 보장하지 않는다. |
| 고객 요구·기술지원과 공급 조율 | 제품·데이터시트 이해, 기술문의·가이드 작성, 고객·공급사 소통, 부품 구매·재고 관리 | [060](sojafit-domain-jobs-2026-11-12.md#job-060), [065](sojafit-domain-jobs-2026-11-12.md#job-065), [066](sojafit-domain-jobs-2026-11-12.md#job-066), [070](sojafit-domain-jobs-2026-11-12.md#job-070) | 근거를 검토자에게 전달하고 승인 후 견적을 기록하는 사용 맥락과 연결된다. 구매·주문을 자동 처리한다는 뜻은 아니다. |

#### 분석에 사용한 공고 50개 링크

표의 번호는 [원 조사서](sojafit-domain-jobs-2026-11-12.md)의 개별 업무·요건·확인 한계로 연결된다. 공고 원문은 외부 게시처로 연결되며, 마감·삭제·로그인·접근 제한 여부를 보장하지 않는다.

| 번호 | 역할·후보 그룹 | 개별 공고 |
|---:|---|---|
| [001](sojafit-domain-jobs-2026-11-12.md#job-001) | SECA · Forward Deployed AI Engineer | [공고 원문](https://secalabs.com/kr/careers) |
| [002](sojafit-domain-jobs-2026-11-12.md#job-002) | 알세미 · AI Agent Engineer | [공고 원문](https://alsemy.career.greetinghr.com/ko/o/241359) |
| [003](sojafit-domain-jobs-2026-11-12.md#job-003) | 딥오토 · [신입/경력] AI Platform Engineer | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50002221) |
| [004](sojafit-domain-jobs-2026-11-12.md#job-004) | 딥오토 · [전환형 인턴] AI Engineer | [공고 원문](https://deepauto-ai.career.greetinghr.com/ko/o/232237) |
| [005](sojafit-domain-jobs-2026-11-12.md#job-005) | 디밀리언 · AI Agent Engineer(경력/신입) | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50127329) |
| [006](sojafit-domain-jobs-2026-11-12.md#job-006) | 마키나락스 · [FDE] Forward Deployed Engineer - LLM (창원) | [공고 원문](https://makinarocks.career.greetinghr.com/ko/o/207418) |
| [007](sojafit-domain-jobs-2026-11-12.md#job-007) | 인터엑스 · [창원] AI Agent Engineer | [공고 원문](https://interxlab.career.greetinghr.com/ko/o/238769) |
| [008](sojafit-domain-jobs-2026-11-12.md#job-008) | 엣지크로스 · AI SW Engineer (Agentic AI) | [공고 원문](https://www.saramin.co.kr/zf_user/jobs/view?rec_idx=55275909) |
| [009](sojafit-domain-jobs-2026-11-12.md#job-009) | 럭스로보 · ML/AI 엔지니어 (LLM 기반 PCB 자동배치) | [공고 원문](https://www.saramin.co.kr/zf_user/jobs/view?rec_idx=55417933) |
| [010](sojafit-domain-jobs-2026-11-12.md#job-010) | 디노티시아 · [Business] AI Engineer (FDE, Forward Deployed Engineer) (채용연계형 인턴) | [공고 원문](https://dno.career.greetinghr.com/ko/o/242431) |
| [011](sojafit-domain-jobs-2026-11-12.md#job-011) | 디노티시아 · [Product] AI Agent Development Engineer | [공고 원문](https://dno.career.greetinghr.com/ko/o/226945) |
| [012](sojafit-domain-jobs-2026-11-12.md#job-012) | 디노티시아 · [Product] Vector Database Engineer | [공고 원문](https://dno.career.greetinghr.com/ko/o/200913) |
| [013](sojafit-domain-jobs-2026-11-12.md#job-013) | 엑시나 · [SW] Software Engineer, Vector Search | [공고 원문](https://xcena.career.greetinghr.com/ko/o/167324) |
| [014](sojafit-domain-jobs-2026-11-12.md#job-014) | 원프레딕트 · Backend Developer(백엔드 개발자) | [공고 원문](https://onepredict.career.greetinghr.com/ko/o/200859) |
| [015](sojafit-domain-jobs-2026-11-12.md#job-015) | 제론 · AI Agent SW 개발자/K-디지털트레이닝 | [공고 원문](https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=55313202) |
| [016](sojafit-domain-jobs-2026-11-12.md#job-016) | 콘센트릭스서비스코리아 · LLM/Agent Engineer(과장·차장) | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50077245) |
| [017](sojafit-domain-jobs-2026-11-12.md#job-017) | 팀워크 · AI 엔지니어(AI Engineer), 2년 이상 | [공고 원문](https://www.wanted.co.kr/wd/366126) |
| [018](sojafit-domain-jobs-2026-11-12.md#job-018) | 에이아이스타 · LLM·RAG 엔지니어(NLP·AI 검색·Vector DB) - 신소재 R&D AI 스타트업 | [공고 원문](https://zighang.com/recruitment/45fb791f-ec4e-406e-a125-5b813d010d73) |
| [019](sojafit-domain-jobs-2026-11-12.md#job-019) | HDC랩스 · AI LAB팀 AI 에이전트(AX) 개발 경력 | [공고 원문](https://www.zighang.com/recruitment/bbaf98a9-a6f2-4bc3-83c5-3cf341f38f93) |
| [020](sojafit-domain-jobs-2026-11-12.md#job-020) | 로자이크(ROSAIC) · 제조 AX Physical AI 엔지니어 | [공고 원문](https://www.zighang.com/recruitment/67451657-a562-4b30-bf93-e504affc4d73) |
| [021](sojafit-domain-jobs-2026-11-12.md#job-021) | 반석써치(의뢰기업 비공개) · AI 엔지니어 / 아키텍쳐 설계 / 거버넌스 [연구소] | [공고 원문](https://zighang.com/recruitment/936e931f-918c-4d91-b463-f06a12bc5d19) |
| [022](sojafit-domain-jobs-2026-11-12.md#job-022) | 한화시스템 · VLM Project Manager 경력사원 | [공고 원문](https://gwona.com/jobs/18334) |
| [023](sojafit-domain-jobs-2026-11-12.md#job-023) | SECA · Design Automation Engineer | [공고 원문](https://secalabs.com/kr/careers) |
| [024](sojafit-domain-jobs-2026-11-12.md#job-024) | 뉴로코어 · AI Engineer(LLM·Knowledge) | [공고 원문](https://career.rememberapp.co.kr/job/posting/338920) |
| [025](sojafit-domain-jobs-2026-11-12.md#job-025) | 리빈에이아이 · AI 엔지니어 (신입) — RAG / 검색 시스템 개발 | [공고 원문](https://www.wanted.co.kr/wd/366428) |
| [026](sojafit-domain-jobs-2026-11-12.md#job-026) | 럭스로보 · AI개발자 (부품 데이터시트 분석/OCR) | [공고 원문](https://jumpit.saramin.co.kr/position/48265516) |
| [027](sojafit-domain-jobs-2026-11-12.md#job-027) | 갓테크 · AI 엔지니어 (ML/LLM/RAG) | [공고 원문](https://www.saramin.co.kr/zf_user/jobs/view?rec_idx=54224412) |
| [028](sojafit-domain-jobs-2026-11-12.md#job-028) | 넥스트랩 · LLM RAG 시스템 개발자 채용 | [공고 원문](https://jumpit.saramin.co.kr/position/53527987) |
| [032](sojafit-domain-jobs-2026-11-12.md#job-032) | 대원씨티에스 · B2B업무시스템 기반 풀스택개발자 | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50349614) |
| [034](sojafit-domain-jobs-2026-11-12.md#job-034) | 에너비스 · 전기·전자·통신 제품 개발 연구원 (HW/SW) | [공고 원문](https://www.jinhakpro.com/recruit/49347) |
| [036](sojafit-domain-jobs-2026-11-12.md#job-036) | 엣지크로스 · 임베디드 소프트웨어 개발자(신입) | [공고 원문](https://www.wanted.co.kr/wd/383980) |
| [038](sojafit-domain-jobs-2026-11-12.md#job-038) | 에이아이오 · Storage Product Engineer | [공고 원문](https://www.wanted.co.kr/wd/386113) |
| [039](sojafit-domain-jobs-2026-11-12.md#job-039) | 닷 · 하드웨어 엔지니어(회로설계) | [공고 원문](https://www.wanted.co.kr/wd/124026) |
| [040](sojafit-domain-jobs-2026-11-12.md#job-040) | 메타파머스 · 로봇 하드웨어 엔지니어 | [공고 원문](https://www.wanted.co.kr/wd/396200) |
| [043](sojafit-domain-jobs-2026-11-12.md#job-043) | 옵티코어 · H/W, 데이터센터 개발팀 [경력 및 신입] | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50199257) |
| [044](sojafit-domain-jobs-2026-11-12.md#job-044) | 웨어러블에이아이 · 임베디드 하드웨어 설계 엔지니어 (3년~) | [공고 원문](https://jumpit.saramin.co.kr/position/55405027) |
| [045](sojafit-domain-jobs-2026-11-12.md#job-045) | 큐쓰리모션랩 · 하드웨어(HW) 회로설계 및 PCB 개발 담당자 | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50102164) |
| [046](sojafit-domain-jobs-2026-11-12.md#job-046) | 피닉슨컨트롤스 · 연구개발본부 HW팀 신입/경력사원 | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50216279) |
| [047](sojafit-domain-jobs-2026-11-12.md#job-047) | 유니솔렉 · 전자공학(하드웨어) 엔지니어 | [공고 원문](https://www.jinhakpro.com/recruit/48531) |
| [050](sojafit-domain-jobs-2026-11-12.md#job-050) | NEXTLAB · 회로개발자 | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50148927) |
| [052](sojafit-domain-jobs-2026-11-12.md#job-052) | 모빌린트 · [AI반도체] H/W System Design Engineer (Senior) | [공고 원문](https://www.wanted.co.kr/wd/285749) |
| [055](sojafit-domain-jobs-2026-11-12.md#job-055) | 에이스 디바이스 · 하드웨어 회로 설계 및 개발 | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/49945440) |
| [057](sojafit-domain-jobs-2026-11-12.md#job-057) | 코넥티브 · 수술로봇 회로 설계 및 개발자 | [공고 원문](https://www.wanted.co.kr/wd/326917) |
| [058](sojafit-domain-jobs-2026-11-12.md#job-058) | 퀀텀에어로 · 시니어 임베디드 하드웨어 개발자 | [공고 원문](https://www.wanted.co.kr/wd/382361) |
| [059](sojafit-domain-jobs-2026-11-12.md#job-059) | 티와이모듈코리아 · 하드웨어/펌웨어 개발 (신입/경력) | [공고 원문](https://www.jinhakpro.com/recruit/45325) |
| [060](sojafit-domain-jobs-2026-11-12.md#job-060) | 로아스 · FAE 엔지니어 (Field Application Engineer) | [공고 원문](https://www.wanted.co.kr/wd/396400) |
| [064](sojafit-domain-jobs-2026-11-12.md#job-064) | 유니퀘스트 · 반도체 기술영업(FSE) - Infineon 제품 | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50198937) |
| [065](sojafit-domain-jobs-2026-11-12.md#job-065) | 유니퀘스트 · 반도체 기술영업(FSE) - Renesas | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50265165) |
| [066](sojafit-domain-jobs-2026-11-12.md#job-066) | 유니퀘스트 · Clock 및 Timing 기술지원(FAE) | [공고 원문](https://www.jobkorea.co.kr/Recruit/GI_Read/50220300) |
| [070](sojafit-domain-jobs-2026-11-12.md#job-070) | 와이제이컴 · 반도체 전자부품 구매 및 자재 관리 전문가 | [공고 원문](https://lab.incruit.com/jobs/2610140001244) |


---

## 2. 사용자·지불 주체: 확인 사실과 가설의 구분

`docs/reference/evaluation-prep.md` 지침에 따라, 이미 데이터·경험으로 확인한 사실과 아직 외부 인터뷰로 검증하지 못한 가설을 분리한다.

### 2-1. 확인된 사실 (Verified Facts)

1. **팀원의 실제 회로 설계·수리 경험 (`docs/TOPIC.md`)**:
   - ATtiny85 기반 소형 MCU 회로를 다룰 때 제너 다이오드·쇼트키 다이오드가 회로에서 맡은 정확한 역할과 대체 시 지켜야 할 필수 정격 조건을 바로 판단하기 어려워, 부품 수급이나 크기 변경이 필요해도 원본 회로도의 품번을 그대로 따라 썼다.
2. **공개 KiCad 회로 151개(다이오드 554개) 넷리스트 실측 (`docs/TOPIC.md` 각주 [4])**:
   - 공개 ATtiny85 계열 KiCad 프로젝트 151개(중복 파일 제외 다이오드 554개, 역할 후보 75개)를 전수 집계한 결과, 5V급 저전압 회로에서도 `1N4148`(100V)이 53개(9개 저장소), `1N4007`(1000V)이 11개(3개 저장소)로 반복 사용되었다.
   - 즉 실무·오픈소스 하드웨어 모두 "회로 역할에 필요한 최소 정격"을 다시 계산하기보다 익숙한 과사양 품번이나 기존 BOM 품번을 관성적으로 재사용하고 있음이 데이터로 확인된다.
3. **데이터시트 표 구조의 조건 결합성 (`EVAL_REPORT.md` 1장, `evals/dataset_v1.jsonl`, `evals/dataset_v2.jsonl`)**:
   - Taiwan Semiconductor(TSC) 다이오드 데이터시트 1,360건(품번 9,589개)에서 한 문서는 평균 7개 이상의 형제 품번을 한 표에 묶어 기술하며, 정격 숫자(예: `VZ 3.42~3.78V`, `IR 500µA`, `CJ 55pF`)는 반드시 시험 조건(`TA=25°C`, `IZT=5mA`, `30ms 펄스`, `TYP` 대 `MAX`) 및 표 밖 주석(예: `AEC-Q101`, 서지 파형)과 함께 읽어야만 대체 가능 여부를 판정할 수 있다.
4. **기존 대체재의 기능 경계 확인 (`docs/TOPIC.md` 각주 [3])**:
   - 유통사(Mouser, DigiKey) 파라미터 필터와 제조사 cross-reference 도구는 **원래 부품의 사양 이상**만 대조하며 동등성을 보증하지 않는다고 명시한다.
   - AI 설계 보조 도구(Flux, Zenode)는 사양 기반 대체품 검색을, SheetsData MCP는 사용자가 직접 입력한 조건의 정격 점검을 제공하지만, **KiCad 넷리스트의 연결 구조에서 부품 역할을 읽고 → 역할별 필수 조건을 도출해 → 데이터시트 쪽·표·행 인용과 함께 5종 판정(`IDENTICAL` / `SPEC_EQUIVALENT` / `ROLE_SUFFICIENT` / `NOT_SUFFICIENT` / `NOT_VERIFIED`)을 내리는 흐름**은 확인되지 않았다.
5. **데이터시트 저작권·약관 경계 (`data/corpus/CORPUS.md`, `SPEC.md` 6절)**:
   - TSC(1,360건)와 Infineon은 비상업·비수정·출처 표기 조건으로 복제·배포를 허용하는 반면, TI·Diodes·Vishay·ST·Nexperia·PANJIT은 재배포를 금지한다. Mouser Search API 역시 가격·재고 응답의 영구 DB 저장을 약관으로 금지한다([ADR 0009](../adr/0009-mouser-응답은-저장하지-않는다.md)).

### 2-2. 미검증 가설 (Unverified Hypotheses — 사실로 단정하지 않음)

| 구분 | 가설 내용 | 왜 아직 가설인가 | 검증 방법(남은 확인) |
|---|---|---|---|
| 문제 가설 H1 | 하드웨어 개발자가 사양만 맞춘 대체품을 고르다 시험 조건(`TA` 대 `TJ`, 펄스 폭, `TYP` 대 `MAX`)이나 패키지 차이를 놓쳐 재작업·재발주를 겪는다 | 팀원 경험과 공개 회로 554개 집계는 확인했으나, 외부 기업 엔지니어의 건당 소요 시간·오선정 빈도는 정량 인터뷰 전이다 | 외부 하드웨어/임베디드 경험자 1명 이상 검토(E1-5) |
| 지불 주체 가설 H2-A | 시제품·소량 양산을 반복하는 소규모 하드웨어 개발팀·기업이 엔지니어 검토 시간 단축과 BOM 리스크 감소를 위해 유료 구독(B2B SaaS)한다 | 실제 유료 과금 실험이나 구매 의사결정자 인터뷰를 수행하지 않았다 | 외부 검토 시 지불 의향 및 도입 장벽(보안·코퍼스 범위) 질문 |
| 지불 주체 가설 H2-B | 부품 유통사(Mouser, DigiKey 등)가 판정 완료 후 견적→주문 전환을 높이는 고객 확보용 도구로 비용을 부담한다(참고: Renesas의 Altium 인수 등 설계→조달 결합 사례) | 유통사 제휴나 실제 주문 전환율을 측정할 수 없는 교육용 프로젝트 범위다 | 확장 가설로만 명시하고 완료 사실로 주장하지 않는다 |
| 지불 주체 가설 H2-C | 제조AX 공급사가 공장·설비 보전팀의 단종 보드 수리·대체 소자 검토 내부 도구로 납품한다 | 채용 공고에서 제조AX 수요는 확인했으나 보전 부서 실사용 테스트는 전이다 | 포트폴리오·발표에서 확장 적용처 가설로 구분해 제시 |

---

## 3. 목표 사용자 페르소나와 반복 문서 업무

### 3-1. 페르소나 정의

| 항목 | 페르소나 A — 주 사용자 (탐색·검토자) | 페르소나 B — 승인·의사결정자 (책임자) |
|---|---|---|
| 역할 | 소형 MCU·임베디드 보드 하드웨어 개발자 (경력 1~4년, 소규모 HW팀 또는 메이커/스타트업) | 하드웨어 팀 리드 / 연구소 파트장 (BOM 승인·시제품 발주 책임) |
| 반복 문서 업무 | 기존 KiCad 보드의 다이오드가 단종·재고 부족·패키지 변경·원가 절감 대상이 될 때마다, 회로도/넷리스트에서 역할을 확인하고 후보 데이터시트 PDF 3~10개의 정격표·특성곡선·각주·패키지 치수를 대조해 대체 가능 품번을 추린다 | 개발자가 올린 대체 부품 후보와 견적서를 보고, ① 원래 회로 역할에 비춰 전압·전류·속도 여유율이 충분한지, ② 데이터시트 시험 조건이 실제 보드 조건과 맞는지, ③ 패드(풋프린트) 수정이 필요한지 확인한 뒤 발주·견적 저장을 승인한다 |
| 현재 해결 방법 | 유통사(Mouser/DigiKey) 필터에서 원래 부품과 전압·전류가 같거나 높은 부품을 검색한 뒤, PDF를 하나씩 열어 `Ctrl+F`로 `VRRM`, `VF`, `trr`, `VZ`를 찾고 엑셀/메모장에 수기로 비교표를 만든다 | 개발자가 구두나 메신저로 가져온 품번의 데이터시트 PDF를 다시 열어 1~2쪽 정격표와 패키지 도면을 눈으로 재확인한다 |
| 핵심 불편 (Pain Point) | ① 원래 부품이 과사양(`5V` 회로에 `1000V 1N4007`)이면 사양 필터만으로는 더 작고 적합한 후보를 못 찾음<br>② 한 PDF에 `1N5817/1N5818/1N5819`나 `BZT52C2V4~C39`가 함께 들어 있어 행·열을 잘못 읽거나 `TYP` 값을 `MAX` 보장값으로 착각하기 쉬움<br>③ 범용 챗봇에 물어보면 없는 품번을 지어내거나 데이터시트 출처(쪽·표·행) 없이 그럴듯하게 단정함 | ① 개발자가 어떤 데이터시트 몇 쪽·어느 표 행을 근거로 판정했는지 추적하기 어려움<br>② 온도 조건(`TA=25°C` 대 `TJ=25°C`)이나 미확인 조건(`USB D+/D-` 정전용량 등)이 빠진 채 "대체 가능"으로 올라오면 시제품 불량으로 이어짐 |
| SojaFit에 기대하는 것 | 넷리스트와 대상 부품(`D1`)만 지정하면 회로 연결에서 역할과 필수 조건을 도출하고, 코퍼스 데이터시트의 정확한 쪽·표·행을 인용해 후보별 판정 5종을 내주며, 조건이 부족하면 억지 추천 대신 무엇이 부족한지 알려 주는 것 | 판정마다 인용된 데이터시트 쪽·표·행과 결정적 수치 비교 결과를 한눈에 검수하고, 내가 판정 결과를 승인한 뒤 견적을 DB에 저장·이력화하는 것 |

---

## 4. 고객 여정 맵 (Customer Journey Map)

교안의 단순 노드 흐름(User Flow)과 구분하여, 사용자가 부품 변경 문제에 부딪혀 최종 견적을 승인하기까지 겪는 **6단계 행동·접점·불편(Pain Point)·감정/위험·SojaFit의 개입과 설계 근거**를 정리한다.

| 단계 | 1. 문제 발생 (단종·수급·변경) | 2. 회로 역할 파악 | 3. 대체 필수 조건 설정 | 4. 후보 탐색 및 데이터시트 대조 | 5. 대체 적합성 판정 및 리스크 확인 | 6. 견적서 검토·승인 및 이력 재사용 |
|---|---|---|---|---|---|---|
| **사용자 행동** | BOM 점검 중 특정 다이오드(`D1`, `D2`, `D3`)의 재고 소진·단종·크기 축소 필요를 발견함 | KiCad 회로도와 넷리스트(`.net`)를 열어 해당 다이오드의 애노드(A)·캐소드(K)가 어느 넷(`VCC`, `GND`, `USB D-`, 코일 등)에 연결됐는지 추적함 | 역할(역극성 보호, 플라이백, 제너 클램프, 고속 스위칭)에 따라 필요한 `VRRM`, `IF`, `VF`, `VZ`, `trr`, `CJ`와 여유율을 정함 | 후보 품번 데이터시트 PDF 여러 개를 내려받아 `ABSOLUTE MAXIMUM RATINGS`, `ELECTRICAL CHARACTERISTICS`, `ORDERING INFORMATION`, 외형 치수 표를 대조함 | 후보가 원래 품번과 동일품인지, 사양 동등인지, 사양은 낮아도 회로 역할상 충분한지, 기판 수정이 필요한지 결론을 냄 | 선정 근거와 수량·단가를 묶어 팀 리드에게 공유하고, 승인된 대체안만 BOM·견적 이력으로 남김 |
| **접점 (Touchpoint)** | BOM 시트, 유통사 재고 알림 | KiCad 회로도, `.net` 넷리스트, `connections.json` | 설계 가이드, 엔지니어 경험, 이전 프로젝트 메모 | 제조사(TSC 등) 데이터시트 PDF, 유통사 검색창, 범용 챗봇 | 엑셀 비교표, 데이터시트 각주·특성 곡선 | 팀 메신저/리뷰 회의, 견적서 양식 |
| **현재 방식의 Pain Point** | 당장 대체 가능한 후보가 사내에 있는지, 어디서부터 찾아야 할지 막막함 | 오픈소스·외부 레퍼런스 보드는 왜 그 다이오드를 썼는지 주석이 없어, 원래 품번(`1N4007` 1000V 등)의 사양을 무조건 따라가게 됨 | 역할에 맞는 여유율 기준이 사람마다 다르고, 주변 온도(`TA`)·펄스 폭·신호선 정전용량 같은 숨은 조건을 빠뜨림 | ① 한 PDF 안의 형제 품번 행(`1N5817` 대 `1N5819`) 혼동<br>② `TYP` 값과 `MAX` 보장값 혼동<br>③ 개정판(`G1804` 대 `G2611`)·주문코드(`H` = AEC-Q101) 차이 누락 | 범용 챗봇은 없는 품번을 추천하거나 조건이 부족해도 "가능하다"고 단정함. 반대로 유통사 사양 필터는 5V 회로의 1000V 다이오드 대체품으로 또 1000V만 찾아줌 | 근거 페이지·표가 기록되지 않아 승인자가 데이터시트를 처음부터 다시 읽어야 하고, 승인 전 초안이 확정본과 섞임 |
| **실패 시 위험** | 일정 지연 | 역할 오판(제너 클램프를 일반 정류기로 오인 등) | 과사양 고착 또는 정격 부족으로 인한 소자 소손 | 잘못된 표 행·전형값 인용으로 인한 시제품 동작 불량 | 스루홀(`DO-35`)과 표면실장(`SOD-123F`) 패키지 차이를 놓쳐 보드 조립 불가 | 미승인 견적·오판정 사례가 다음 보드 설계에 그대로 재사용됨 |
| **SojaFit의 개입 (해결 방식)** | 로그인 후 회로 넷리스트와 대상 부품(`D1`) 및 질문 입력(`POST /api/auth/login`, 그래프 `read_input`) | `read_input`이 `connections.json`에서 대상 부품과 2단계 이웃 넷 경로(예: `J1 → S1 → D1 → F1 → RAW`)를 결정적으로 추출해 `[넷리스트]` 근거로 제공 | 회로 역할 설명과 역할별 필수 조건 규칙(`SPEC.md` 2·5절)을 분리하고, 부족한 사용자 동작 조건(`TA`, 차단 전류·펄스 폭 등)은 임의 가정 없이 되묻거나 `NOT_VERIFIED`로 분류 | 표지 품번 색인(`parts`) + 하이브리드 검색(`retrieve`) + 형제 품번 행·타 개정판 결정적 제거(`grade`의 `other_part_row`·`wrong_revision`) + 영문 파라미터 재작성(`rewrite`, 최대 2회 검색) | 수치·단위 비교는 `backend/judge/` 코드로만 수행하고, 생성 노드는 통과 청크만 인용해 판정 5종(`IDENTICAL` / `SPEC_EQUIVALENT` / `ROLE_SUFFICIENT` / `NOT_SUFFICIENT` / `NOT_VERIFIED`)과 기판 수정 필요 여부 및 `"같은 동작은 보장하지 않는다"` 고지를 출력 | 완료 판정에서 승인 가능한 후보를 별도 승인 API로 승인하면 사용자별 승인 사례를 저장하고, 승인 ID로 가격 없는 견적을 저장한다. 견적 승인 `interrupt`와 다음 분석에서 승인 사례 재참조는 현재 미구현이다. |

---

## 5. 범용 챗봇과 동일 질문 5개 비교 설계 (`EVAL_REPORT.md` 10장 연결)

### 5-1. 비교 목적과 측정 항목 (`docs/TOPIC.md`, `COURSE_GUIDE.md#h01`)

범용 챗봇(코퍼스·넷리스트 검증 경계가 없는 상태의 일반 LLM 응답)과 SojaFit에 **동일한 질문 5개**를 넣어 아래 4가지를 나란히 비교한다.

1. **근거 인용의 검증 가능성**: 실제 데이터시트 파일명·개정코드·쪽·표·행 또는 넷리스트 연결 경로를 인용하는가, 그리고 인용 번호가 실제 검색 청크에 존재하는지 코드로 검증하는가?
2. **형제 품번·시험 조건·보장값(`MAX` 대 `TYP`) 구분**: 한 데이터시트 안의 다른 품번 행이나 전형값(`TYP`)을 보장 최댓값(`MAX`)으로 섞어 쓰지 않는가?
3. **확인 안 됨(`NOT_VERIFIED`) 및 거절 처리**: 사용자 동작 조건이 부족하거나(`n01`), 문서에 보장 최댓값 속성이 없거나(`n14`), 코퍼스에 없는 품번(`e07`/`n09`)일 때 억지 추측 대신 정확히 멈추는가?
4. **역할 기반 대체 판정**: 원래 부품(`1N400x/SM4002` 또는 `1N5819` 40V)보다 정격 숫자는 낮아도 회로 사용 조건(12V 전원, 여유율 반영 필수 15V 이상, 단발 피크 80mA)에서 역할상 충분(`ROLE_SUFFICIENT`)한 후보(`1N5817` 20V)를 근거와 함께 판정할 수 있는가?

### 5-2. 대표 비교 질문 5개 선정 (동결 `v1` 및 `v2`)

| # | 문항 ID | 검증하는 핵심 차별점 | 질문 요약 | 정답 및 판정 기준 |
|---|---|---|---|---|
| 1 | `draft30-e01` (v1 관련 `role`) | **KiCad 넷리스트 연결 기반 회로 역할 파악** | SparkFun Breadboard Supply에서 `D1(1N4001)`은 어떤 넷 사이에 놓여 있고 무슨 역할을 해? | `J1(배럴잭 PWR) → S1 → D1(A: Net-(S1-S), K: RAW) → F1 → IC1(LM7805)` 직렬 입력 경로를 `[넷리스트]`로 인용해 **역극성 보호 다이오드**로 설명 |
| 2 | `draft30-e03` (v1 관련 `rating`) | **다중 품번 데이터시트에서 단일 품번 정격 추출** | Adafruit MOSFET Driver의 `D3` 후보인 `TSC 1N5817`은 반복 피크 역전압(`VRRM`)이 몇 V야? | `1N5817 SERIES_H2104.pdf` 1쪽 `ABSOLUTE MAXIMUM RATINGS (TA=25°C)` 표에서 `1N5818(30V)`·`1N5819(40V)` 행을 섞지 않고 **`1N5817`의 `VRRM = 20V`**를 인용 |
| 3 | `draft50-n01` / `draftv2-n03` (조건 부족 vs 완비) | **시험 조건(`TA` 대 `TJ`) 확인과 역할 기반 대체(`NOT_VERIFIED` 대 `ROLE_SUFFICIENT`)** | MOSFET Driver `D3`를 12V·80mA 플라이백 조건에서 `1N5817(20V)` 등으로 바꿀 수 있는가? (`n01`: `TJ=25°C`만 제시 / `draftv2-n03`: `TA=25°C` 및 `8.3ms` 단발 피크 `80mA` 명시) | `n01`은 `H2104` 1쪽 정격 기준인 `TA=25°C` 조건이 빠져 **`NOT_VERIFIED`**로 보류하고 `TA`를 되묻는다. `draftv2-n03`은 `TA=25°C`가 주어져 필수 `15V`·`80mA` 이상이므로 `1N5817(20V)`을 **`ROLE_SUFFICIENT`(역할상 충분, 기판 수정 필요)**로 판정 |
| 4 | `draft50-n14` (v1 비관련 `missing_attribute`) | **문서에 없는 보장 최댓값(`MAX`) 요구 시 거절 (그래프 곡선 추정 금지)** | ATtiny85 보드 `D1` 후보인 `TSC BZT52C3V6(G1804)`의 `1MHz, VR=1V` 조건 접합 정전용량 **보장 최댓값(MAX)**은 몇 pF야? | `BZT52C2V4 SERIES_G1804.pdf` 1~2쪽 표에는 접합 정전용량 `MAX` 보장값 행이 없고 3쪽 `Fig.5 Typical Junction Capacitance` 곡선만 있으므로, 곡선 눈금을 보장 최댓값으로 읽지 않고 **문서로 확인 안 됨(거절)**으로 답함 |
| 5 | `draft30-e07` / `draft50-n09` (v1 비관련 `unknown_entity`) | **코퍼스 미수록 품번(`SS1P3L`, `BAT85`) 환각 차단 및 단서 요청** | `SS1P3L`(`e07`) 또는 `BAT85`(`n09`)의 최대 역전압과 순방향 전류 정격은 얼마야? | 제공 코퍼스(`data/manifest.jsonl` 1,360건)에 없으므로 사전 학습 기억으로 수치를 답하지 않고, `search` 0장 → `refuse` 노드로 즉시 거절하며 부품 윗면 마킹·데이터시트·주문 코드 단서를 요청 |

---

## 6. 외부 검토 1명 점검 계획 및 기록 양식 (E1-5)

D10 최종 정리 전 외부 시선 1명(전자·하드웨어 또는 타 조/현업 개발자)에게 서비스 화면·근거 인용·판정 경계를 보여 주고 아래 양식으로 피드백과 반영 여부를 남긴다(현재 상태: **검토 전 양식 준비 완료**).

| 항목 | 기록 내용 (검토 수행 후 기입) |
|---|---|
| 검토 일시·검토자 배경 | (예: 2026-11-XX, 임베디드/하드웨어 개발 유경험자 1명 — 실명 대신 역할·경력 표기) |
| 검토에 사용한 시나리오 | 정상 판정 1건(`e03` 또는 `draftv2-n03`), 조건 부족/보장값 부재 거절 1건(`n01` 또는 `n14`), 승인 대기 1건 |
| 질문 1: 인용된 데이터시트 쪽·표·행만으로 판정을 신뢰할 수 있는가? | (검토자 의견 기록란) |
| 질문 2: "문서로 확인 안 됨(`NOT_VERIFIED`)"으로 멈추는 경계가 실무에서 납득되는가, 너무 잦은가? | (검토자 의견 기록란) |
| 질문 3: 지불 주체 가설(개발팀 구독 vs 유통사 제공) 중 어느 쪽이 현실적인가? | (검토자 의견 기록란) |
| 수용해 코드·문서에 반영한 점 / 반영하지 않은 점과 이유 | (반영 커밋·문서 절 또는 Out of Scope 사유 기록란) |

---

## 7. `EVAL_REPORT.md` 10장(대체재와의 비교) 및 11장(현재 서비스의 가장 큰 약점) 정리본

조장이 `EVAL_REPORT.md` 10장·11장에 그대로 반영할 수 있도록 5문항 대조표와 현재 서비스의 가장 큰 약점 4가지를 함께 기록합니다.

### 7-1. 대체재와의 비교 (`EVAL_REPORT.md` 10장 반영안)

**2026-11-12 정본:** `EVAL_REPORT.md` 10장의 실제 비교 대상 Codex는 범용 코딩 에이전트다. 비교에 사용한 Codex 응답은 [입력](../../evals/samples/v3_50_codex_paste.md)과 [답변](../../evals/results/graph/2026-11-12-codex-v3-50/codex_answers.md)을 참고하며 자동 채점하지 않았다. v3 정답은 출제와 분리된 자동 정답 세션의 초안이며, 1차 판정자 심태현·2차 판정자 하정운으로 2026-11-12 정정한다.([평가셋 안내](../../evals/guides/dataset-guide.md)). 평가 리포트와 ADR 0015의 기존 단독 판정 서술도 같은 내용으로 정정한다. v3 정답 초안이 Codex 세션에서 작성됐다고 확인했다. 작업 원본은 저장소 밖에 있으며, 비교 대상도 Codex이므로 결과 해석에서 이를 고려한다. v1은 [작업 기록](../worklog/jeongun.md)에 Codex 세션 사용이 명시돼 있다.

정본의 5행에 추가한 **판정 기준**은 [동결 v3 정답](../../evals/dataset_v3.jsonl)의 `expected`를 기준으로 한다. 이 기준은 두 답변의 자동 채점 결과가 아니다.

| 문항 | 판정 기준 |
|---|---|
| v3-01 | 사용 조건에 필요한 전압·전류·서지 조건을 대조하고 역할상 충분 여부와 기판 수정 필요를 구분한다. |
| v3-05 | 25kHz PWM의 요구 역회복 조건을 만족하는지 확인하고 불충족으로 판정한다. |
| v3-10 | 단방향 보호 조건과 허용 클램프 전압을 확인해 양방향 후보를 불충족으로 판정한다. |
| v3-26 | 릴레이 선정은 다이오드 코퍼스 범위 밖이므로 후보를 제시하지 않는다. |
| v3-45 | 지정 판본이 코퍼스에 없으면 다른 개정판의 수치로 대체하지 않는다. |

아래 표는 **11-03 v1/v2 비교 설계·당시 기록**이다.

같은 질문 5개를 범용 챗봇(코퍼스·넷리스트 검증 경계 없이 질문 텍스트만 입력한 일반 LLM 응답)과 우리 서비스(`build_graph`, `anthropic/claude-haiku-5.5` + 하이브리드 검색 + 결정적 필터·인용 검사)에 나란히 넣습니다.

| # | 질문 | 범용 챗봇 | 우리 서비스 | 차이 |
|---|---|---|---|---|
| 1 | **`e01` (회로 역할)**: SparkFun Breadboard Supply에서 `D1(1N4001)`은 어떤 넷 사이에 놓여 있고 무슨 역할을 해? | 보드 이름과 `1N4001` 통념에 기대어 입력 전원 보호용이라고 추정할 뿐, 실제 KiCad 넷리스트의 핀·소자 연결(`J1 → S1 → D1 → F1 → RAW`)은 인용하지 못함 | `read_input`이 `connections.json`에서 `J1(PWR) → S1 → D1(A: Net-(S1-S), K: RAW) → F1 → IC1(LM7805)` 2단계 경로를 추출해 `[넷리스트]` 근거로 넘김 (단, 현재 `generate.md` v1은 "근거에 적힌 내용만 쓴다" 제약 때문에 11-03 실측에서 연결만 있고 역할 단어가 없다며 `문서로 확인 안 됨`으로 답해 S2 Skill·역할 규칙 연결이 필요함) | 범용 챗봇은 회로도를 보지 않고 통념으로 답하고, 우리 서비스는 실제 넷리스트 연결 경로만 근거로 강제함 |
| 2 | **`e03` (형제 품번 표 정격)**: Adafruit MOSFET Driver `D3` 후보인 `TSC 1N5817`은 역전압(`VRRM`)을 몇 V까지 견뎌? | `1N5817`이 20V 쇼트키라는 사전 지식으로 `20V`를 답하지만, 어느 제조사·개정판(`H2104`) 몇 쪽 표인지 출처를 대지 못하거나 `1N5817~1N5819(20~40V)` 시리즈 설명을 섞어 답함 | 하이브리드 검색(`DEMO_MODE=0`, 11-03 실측)이 `1N5817 SERIES_H2104.pdf` 1쪽 `ABSOLUTE MAXIMUM RATINGS`의 `VRRM 20V` 청크(1186)를 회수하고, `grade` 노드가 `1N5818(30V)`·`1N5819(40V)` 전용 행을 코드(`other_part_row`)로 제거한 뒤 `[1186]`을 인용해 `VRRM 20 V`로 답함(허위 인용 0건) | 같은 표 안의 형제 품번(`1N5818/5819`) 행을 LLM 전에 코드로 걸러내고 데이터시트 파일·쪽·행 번호를 검증 가능하게 인용함 |
| 3 | **`n01` / `draftv2-n03` (온도 시험 조건과 역할상 충분 판정)**: 12V·80mA 플라이백 `D3`에 `1N5817(20V)`을 써도 돼? (`n01`: `TJ=25°C`만 제시 / `draftv2-n03`: `TA=25°C` 명시) | 원래 부품(`40V` 이상)보다 낮다는 이유로 무조건 불가하다고 답하거나, 반대로 `12V < 20V`라며 데이터시트 기준 조건(`TA=25°C` 대 `TJ=25°C`, `8.3ms` 반정현파) 확인 없이 바로 사용 가능하다고 단정함 | `n01`(`TJ=25°C`만 제시)은 `H2104` 1쪽 정격 기준인 `TA=25°C`가 없음을 들어 `문서로 확인 안 됨(NOT_VERIFIED)`으로 보류하고 `TA` 조건을 요청하며, `draftv2-n03`(`TA=25°C` 명시)은 원래 부품 사양보다 낮아 사양 동등은 아니지만 필수 `15V`·`80mA` 이상이므로 `ROLE_SUFFICIENT`(역할상 충분)로 구분함 | 사양 대조(원래 부품 이상만 허용)나 무조건 통과와 달리, 회로 역할 필수 조건과 데이터시트 시험 조건(`TA`) 충족 여부를 분리해 5종 판정함 |
| 4 | **`n14` (보장 최댓값 부재·곡선 추정 금지)**: `TSC BZT52C3V6(G1804)`의 `1MHz, VR=1V` 접합 정전용량 **보장 최댓값(MAX)**은 몇 pF야? | 타사 `BZT52` 데이터시트 기억이나 3쪽 `Fig.5 Typical Junction Capacitance` 그래프 눈금(수십~수백 pF)을 끌어와 보장 최댓값인 것처럼 숫자를 답함(환각 위험) | `G1804` 1~2쪽 표에 접합 정전용량 `MAX` 보장값 행이 없고 3쪽 `Fig.5`는 전형(`Typical`) 곡선뿐이므로, 전형값·곡선을 보장 최댓값으로 확대 해석하지 않고(`SKILL.md` S1·`generate.md`) `문서로 확인 안 됨`으로 거절함 | 표의 보장 최댓값(`MAX`)과 그래프 전형값(`Typical`)을 엄격히 구분해 근거 없는 정량 보장을 차단함 |
| 5 | **`e07` / `n09` (코퍼스 미수록 품번 거절)**: `SS1P3L`(`e07`) 또는 `BAT85`(`n09`)로 바꾸려는데 역전압·순방향 전류 정격이 얼마야? | 코퍼스 유무와 무관하게 사전 학습 기억으로 Vishay `SS1P3L(30V, 1A)`·Nexperia `BAT85(30V, 200mA)` 정격을 단정해 답하고, 때로 존재하지 않는 접미사 품번을 대체품으로 제시함 | `search` 노드가 표지 품번 색인에서 `parts=['SS1P3L']`/`['BAT85']`를 조회해 0장을 받고, `after_grade`가 재작성이나 생성 LLM 호출 없이 곧바로 `refuse` 노드로 보내 `"코퍼스에서 데이터시트를 찾지 못했습니다"`와 함께 부품 마킹·데이터시트·주문 코드 단서를 요청함(11-03 `e07` 실측 확인) | 검증된 코퍼스에 없는 타사·미수록 품번에 대해 사전 학습 기억으로 답하는 것을 코드 경로에서 원천 차단함 |

### 7-2. 2026-11-03 당시 서비스의 약점 (과거 기록)

1. **생성 프롬프트(`generate.md` v1)의 과도한 축자 제약으로 인한 회로 역할(`role`) 과잉 거절 (`jeongun.md` 11-03 실측)**:
   - `e01`처럼 `read_input`이 넷리스트 연결 경로(`J1 → S1 → D1 → F1 → RAW`)를 정확히 뽑아 넘겨도, `generate.md`의 `"근거에 적힌 내용만 쓴다"` 지시 때문에 모델이 넷리스트에 `"역극성 보호"`라는 글자가 직접 적혀 있지 않다며 `문서로 확인 안 됨`으로 과잉 거절했다. 수치·조건 판정(`backend/judge/`)과 회로 연결 해석 지침(`SKILL.md` S2)을 역할 질문 경로에 연결해야 한다.
2. **첫 검색에서 같은 문서의 범위 요약 청크가 통과하면 세부 정격 행 재검색으로 가지 못하는 문제 (`EVAL_REPORT.md` 3-1·5장)**:
   - 데이터시트 1쪽 `KEY PARAMETERS`의 시리즈 범위 청크(`20 - 40 V`)나 표지 청크(`page=null`)가 상위 5개에 올라와 `grade`를 통과하면, `after_grade`가 재작성(`rewrite`)으로 가지 않고 바로 생성으로 넘어가 개별 품번(`1N5817` = `20V`, 2쪽 `trr`/`IR`) 세부 행을 놓치는 경우가 있다(동결 v1 하이브리드 베이스라인에서 문서 Recall@5 `0.737` 대비 Page Hit@5 `0.368`).
3. **다중 쪽 근거(정격표 + 3쪽 주석 + 5~6쪽 외형 치수/곡선) 동시 회수 및 그래프 곡선 판정 한계**:
   - `k=5` 검색만으로는 1~2쪽 정격표와 3쪽 `Notes`·5~6쪽 `PACKAGE OUTLINE` 청크를 한 번에 모두 담기 어렵고, 데이터시트 그래프 곡선(`Fig.2`, `Fig.5`)에만 있는 값은 텍스트 파싱으로 보장값을 읽을 수 없어 `NOT_VERIFIED`로 멈춰야 한다.
4. **결정적 수치 비교기(`backend/judge/`)·Supervisor 분리·`interrupt` 승인 대기의 본그래프 미연결**:
   - 현재 `main`의 줄기 그래프(`backend/graph/build.py`)는 단일 에이전트 7노드 기준선이며, D4~D5에서 `backend/judge/`(단위 환산·여유율 비교·5종 판정), Supervisor+서브에이전트 컨텍스트 격리, 견적 저장 전 `interrupt` 승인 대기와 사용자별 DB `Store` 장기 기억을 실제로 연결·검증해야 한다.
