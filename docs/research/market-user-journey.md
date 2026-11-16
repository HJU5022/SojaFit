# 문제와 시장 근거

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 정본(평가 1축 '문제와 시장 근거'의 증거 정리). 대체재 비교 결과의 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 10장, 서비스 약점의 정본은 11장
- 관련 문서: [docs/TOPIC.md](../TOPIC.md), [SPEC.md](../../SPEC.md), [EVAL_REPORT.md](../../EVAL_REPORT.md), [docs/reference/evaluation-prep.md](../reference/evaluation-prep.md), [sojafit-domain-jobs-2026-11-12.md](sojafit-domain-jobs-2026-11-12.md), [evidence/EVIDENCE.md](evidence/EVIDENCE.md)

평가 1축(문제와 시장 근거, 15점)의 다섯 항목(채용 공고 50건 분석, 사용자·지불 주체 사실/가설 구분, 반복 문서 업무·페르소나·고객 여정 맵, 범용 챗봇과 동일 질문 5개 비교, 외부 검토 1명 기록)에 대해 확인 사실, 가설, 남은 일을 구분해 적는다.

---
## 1. 목표 직무·산업 채용 공고 분석과 역량 연결

### 1-1. 현재 시장·직무 근거

현재 평가와 발표에서는 [전자부품·제조 기술문서 인접 채용 공고 조사서](sojafit-domain-jobs-2026-11-12.md)에서 선정한 **50개 역할·후보 그룹**을 사용한다. 공고별 URL, 업무·요건과 확인 한계는 조사서와 아래 50개 링크 표에서 확인할 수 있다. 사용자는 2026-11-12에 선정된 50건을 수동 검증하고 모두 이상 없다고 확인했다.

조사서의 원자료 확인 기준은 2026-11-12 KST다. 전자부품 직접 분야와 제조·기술문서 등 인접 분야, 마감된 공고가 포함되고, 동일 역할의 여러 게시처는 한 그룹으로 묶은 경우가 있다. 따라서 이 50개를 모두 전자부품 RAG 개발 공고로 표현하거나 시장 규모·고객 수로 해석하지 않는다. 공고는 이후 변경·마감되거나 접근이 제한될 수 있다.

과거 2026-10-29의 237건 집계는 당시 제출한 [주제서](../TOPIC.md)에 남아 있는 이력이다. 개별 원자료 사본은 [`evidence/`](evidence/EVIDENCE.md)에 있으나 현재 평가·발표의 채용 근거로 사용하지 않으며, 아래 50개와 같은 모집단이라고 보거나 합산하지 않는다.

### 1-2. 50개 채용 역할 분석: 반복 업무와 요구 역량 (2026-11-12 자료)

분석 범위: 아래에 열거한 50개 역할·후보 그룹을 사용했다. 도메인·AI 개발 28개(001~028), 산업 SW·임베디드 4개(032·034·036·038), 회로·부품·하드웨어 13개(039·040·043~047·050·052·055·057~059), 기술지원·기술영업 4개(060·064~066), 부품 구매·공급망 1개(070)다. SojaFit의 기술문서 검색·에이전트뿐 아니라 부품 선정 업무와 접하는 역할을 포함한다. 서로 다른 게시처의 같은 역할은 조사서에서 한 그룹으로 묶었고, 일부는 접근·상세 확인에 한계가 있다. 공고 50건의 모집단은 과거 주제서의 237건 조사와 다르다. 2026-11-12 사용자가 선정된 50건을 수동으로 검증하고 모두 이상 없다고 확인했다. 아래 해석은 각 공고의 업무 요약을 바탕으로 했다.

| 반복 업무 | 확인되는 요구 역량·도구 | 조사서 예시 | SojaFit과의 연결 |
|---|---|---|---|
| 기술문서·도면·데이터시트·BOM을 읽고 구조화 | PDF·문서 파싱, OCR, 데이터 구조화, 원문 위치·단위·조건 보존 | [001](sojafit-domain-jobs-2026-11-12.md#job-001), [004](sojafit-domain-jobs-2026-11-12.md#job-004), [018](sojafit-domain-jobs-2026-11-12.md#job-018), [026](sojafit-domain-jobs-2026-11-12.md#job-026) | 데이터시트 표·조건·출처를 검색 가능한 근거로 다룬다. |
| 문서 근거 검색과 평가 | 청킹·임베딩, 키워드·벡터 검색, 리랭킹, 평가셋과 검색 품질 측정 | [007](sojafit-domain-jobs-2026-11-12.md#job-007), [017](sojafit-domain-jobs-2026-11-12.md#job-017), [018](sojafit-domain-jobs-2026-11-12.md#job-018), [025](sojafit-domain-jobs-2026-11-12.md#job-025) | 문서 검색·리랭킹과 평가셋을 연결한다. 개별 채용 공고와 서비스 성능은 별개의 근거다. |
| 에이전트·API·서비스 구현 | Python, Tool Calling, LangGraph, FastAPI, DB·비동기 처리, 상태 관리와 테스트 | [002](sojafit-domain-jobs-2026-11-12.md#job-002), [003](sojafit-domain-jobs-2026-11-12.md#job-003), [005](sojafit-domain-jobs-2026-11-12.md#job-005), [011](sojafit-domain-jobs-2026-11-12.md#job-011) | 에이전트 흐름과 API를 구성한다. 공고에 나온 모든 도구를 서비스가 구현한 것은 아니다. |
| 회로·부품 검토와 보드 검증 | 회로·PCB 이해, 부품 선정·BOM, Bring-up, 시험·신뢰성 및 변경 관리 | [040](sojafit-domain-jobs-2026-11-12.md#job-040), [044](sojafit-domain-jobs-2026-11-12.md#job-044), [045](sojafit-domain-jobs-2026-11-12.md#job-045), [050](sojafit-domain-jobs-2026-11-12.md#job-050) | 회로 역할을 바탕으로 대체 부품을 검토하는 문제와 맞닿는다. 실제 보드 시험이나 동작을 보장하지 않는다. |
| 고객 요구·기술지원과 공급 조율 | 제품·데이터시트 이해, 고객 기술문의 대응, R&D·구매와 제품 선정 조율, 부품 구매·재고 관리 | [064](sojafit-domain-jobs-2026-11-12.md#job-064), [065](sojafit-domain-jobs-2026-11-12.md#job-065), [066](sojafit-domain-jobs-2026-11-12.md#job-066), [070](sojafit-domain-jobs-2026-11-12.md#job-070) | 근거를 검토자에게 전달하고 승인 후 견적을 기록하는 사용 맥락과 연결된다. 구매·주문을 자동 처리한다는 뜻은 아니다. |

※ 2026-11-16: 위 표 마지막 행의 예시에서 [060](sojafit-domain-jobs-2026-11-12.md#job-060)(로아스 FAE)을 뺐습니다. 조사서에 적힌 060의 업무는 산업 AI·로봇 설치 · PoC · 현장 장애 지원이고 데이터시트나 제품 이해를 적지 않아, "제품·데이터시트 이해"의 근거가 되지 못합니다(강사 11/16 코멘트 ①). 대신 제품문의를 적은 [064](sojafit-domain-jobs-2026-11-12.md#job-064)를 넣었고, 060에서만 나온 "가이드 작성"을 지우고 남은 공고가 적은 업무(064 · 066 고객 기술문의, 065 R&D · 구매와 제품 선정 조율)로 역량 칸을 고쳤습니다. 데이터시트 분석을 직접 적은 공고는 이 행에서 066뿐입니다. 060은 위 분석 범위의 기술지원 역할 4개에는 그대로 남습니다.

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

이미 데이터·경험으로 확인한 사실과 아직 외부 인터뷰로 검증하지 못한 가설을 분리한다(기준: [docs/reference/evaluation-prep.md](../reference/evaluation-prep.md)).

### 2-1. 확인된 사실 (Verified Facts)

1. 팀원의 실제 회로 설계·수리 경험 (`docs/TOPIC.md`):
   - ATtiny85 기반 소형 MCU 회로를 다룰 때 제너 다이오드·쇼트키 다이오드가 회로에서 맡은 정확한 역할과 대체 시 지켜야 할 필수 정격 조건을 바로 판단하기 어려워, 부품 수급이나 크기 변경이 필요해도 원본 회로도의 품번을 그대로 따라 썼다.
2. 공개 KiCad 프로젝트 151개(파일 216개)의 넷리스트 실측 (`docs/TOPIC.md` 각주 [4], 원자료 [`evidence/netlist/manifest_diodes.json`](evidence/netlist/manifest_diodes.json)):
   - 중복 파일을 제외한 다이오드는 554개이고 그중 역할 후보로 검토한 것이 75개다(`summary.diodes_unique_files`, `summary.reviewed_target5_instances_dedup`). 5V급 저전압 회로에서도 `1N4148`(100V)이 53개(8개 저장소), `1N4007`(1000V)이 12개(4개 저장소)로 반복 사용된다(`files[].diodes[].value`를 근사 중복 파일 `near_dup_of` 제외로 집계 [실측]).
   - 오픈소스 하드웨어가 "회로 역할에 필요한 최소 정격"을 다시 계산하기보다 익숙한 과사양 품번이나 기존 BOM 품번을 재사용하는 경향을 보인다.
3. 데이터시트 표 구조의 조건 결합성 (`EVAL_REPORT.md` 1장, `evals/dataset_v1.jsonl`, `evals/dataset_v2.jsonl`):
   - Taiwan Semiconductor(TSC) 다이오드 데이터시트 1,360건(품번 9,589개, `SPEC.md` 6절)에서 한 문서가 평균 7.05개(9,589/1,360) 품번을 한 표에 묶어 기술한다. 정격 숫자(예: `VZ 3.42~3.78V`, `IR 500µA`, `CJ 55pF`)는 시험 조건(`TA=25°C`, `IZT=5mA`, `30ms 펄스`, `TYP` 대 `MAX`)과 표 밖 주석(예: `AEC-Q101`, 서지 파형)과 함께 읽어야 대체 가능 여부를 판정할 수 있다.
4. 기존 대체재의 기능 경계 (`docs/TOPIC.md` 각주 [3], 원자료 [`evidence/candidate-g-market-saturation.md`](evidence/candidate-g-market-saturation.md)):
   - 유통사(Mouser, DigiKey) 파라미터 필터와 제조사 cross-reference 도구는 원래 부품의 사양 이상만 대조하며 동등성을 보증하지 않는다고 명시한다.
   - AI 설계 보조 도구(Flux, Zenode)는 사양 기반 대체품 검색을, SheetsData MCP는 사용자가 직접 입력한 조건의 정격 점검을 제공한다. KiCad 넷리스트의 연결 구조에서 부품 역할을 읽고, 역할별 필수 조건을 도출해, 데이터시트 쪽·표·행 인용과 함께 5종 판정(`IDENTICAL` / `SPEC_EQUIVALENT` / `ROLE_SUFFICIENT` / `NOT_SUFFICIENT` / `NOT_VERIFIED`)을 내리는 흐름은 확인되지 않았다.
5. 데이터시트 저작권·약관 경계: TSC와 Infineon은 비상업·비수정·출처 표기 조건으로 복제·배포를 허용하고, TI, Diodes, Vishay, ST, Nexperia, PANJIT은 재배포를 금지한다(`data/corpus/CORPUS.md`, `SPEC.md` 6절). Mouser Search API는 가격·재고 응답의 영구 DB 저장을 약관으로 금지한다([ADR 0009](../adr/0009-mouser-응답은-저장하지-않는다.md)).

### 2-2. 미검증 가설 (Unverified Hypotheses — 사실로 단정하지 않음)

| 구분 | 가설 내용 | 왜 아직 가설인가 | 검증 방법(남은 확인) |
|---|---|---|---|
| 문제 가설 H1 | 하드웨어 개발자가 사양만 맞춘 대체품을 고르다 시험 조건(`TA` 대 `TJ`, 펄스 폭, `TYP` 대 `MAX`)이나 패키지 차이를 놓쳐 재작업·재발주를 겪는다 | 팀원 경험과 공개 회로 554개 집계는 확인했으나, 외부 기업 엔지니어의 건당 소요 시간·오선정 빈도는 정량 인터뷰 전이다 | 외부 하드웨어/임베디드 경험자 1명 이상 검토(E1-5) |
| 지불 주체 가설 H2-A | 시제품·소량 양산을 반복하는 소규모 하드웨어 개발팀·기업이 엔지니어 검토 시간 단축과 BOM 리스크 감소를 위해 유료 구독(B2B SaaS)한다 | 실제 유료 과금 실험이나 구매 의사결정자 인터뷰를 수행하지 않았다 | 외부 검토 시 지불 의향 및 도입 장벽(보안·코퍼스 범위) 질문 |
| 지불 주체 가설 H2-B | 부품 유통사(Mouser, DigiKey 등)가 판정 완료 후 견적→주문 전환을 높이는 고객 확보용 도구로 비용을 부담한다(참고: Renesas의 Altium 인수 등 설계→조달 결합 사례) | 유통사 제휴나 실제 주문 전환율을 측정할 수 없는 교육용 프로젝트 범위다 | 확장 가설로만 명시하고 완료 사실로 주장하지 않는다 |
| 지불 주체 가설 H2-C | 제조AX 공급사가 공장·설비 보전팀의 단종 보드 수리·대체 소자 검토 내부 도구로 납품한다 | 채용 공고에서 제조AX 수요는 확인했으나 보전 부서 실사용 테스트는 전이다 | 포트폴리오·발표에서 확장 적용처 가설로 구분해 제시 |

### 2-3. 지불 주체 외부 근거 (2026-11-13 조사)

인접 직무 공고 말고 "누가, 얼마를 내는가"를 직접 보여 주는 외부 자료를 찾았다. 원문과 신뢰도 표기는 [`evidence/payer-research-2026-11-13.md`](evidence/payer-research-2026-11-13.md)(번호 G·K는 그 파일의 표 번호)이고, 아래 [원문 확인] 표시는 페이지를 다시 열어 문장을 대조한 것이다.

- **부품 대체·단종 도구는 회사 단위 연 구독으로 팔린다.** Accuris Parts Intelligence는 트라이얼 뒤 송장을 결제하면 연 4,950달러 구독이 되고, 사용자는 권한을 받은 부서(Division/Department) 단위로 정한다(G4) [원문 확인]. SiliconExpert·Z2Data 구독사 대상 가격 맞춤은 최소 계약 연 6,000달러, 회사당 1회다(G5) [원문 확인]. 설계자 개인용은 연 180달러(Siemens PartQuest 공급망 앱, G10) [원문 확인]부터 있다.
- **가격 등급이 올라갈수록 구매·공급망 조직이 대상이다.** Accuris는 하위 등급을 "설계 엔지니어와 소싱 담당", 최상위 등급을 "엔터프라이즈 공급망·구매 조직"용으로 적는다(G6) [원문 확인]. 실명 도입 사례의 인용자도 공급망 디렉터다(G14, 벤더 보도자료).
- **유통사는 지불자가 아니라 무료 제공자다.** Avnet은 설계 도구 애드인에 대체품 검색을 무료로 넣었고(G21), 대형 유통사 Arrow는 SiliconExpert를 소유한다(G22, 원문 미열람). 그래서 H2-B(유통사가 비용을 부담)는 약해졌다. H2-B 참고로 든 Renesas–Altium 인수는 반도체 제조사의 설계 도구 인수라 이 가설의 근거로 약하다.
- **국내에서 유료 단종 도구를 사서 쓰는 곳은 군·방산이다.** 국방기술품질원 기고는 각 군·해병대사령부·기업체가 IHS·A-Brain 등 상용 단종 예측 도구를 쓰고, 상용 도구의 정보 획득률은 최대 50%이며, 한 체계는 단종 미대응 시 20년간 16억 원이 더 든다고 보고한다(K6) [원문 확인, 본문 일부는 요약으로 확인].
- **국내 공공 예산이 단종 대응 개발비를 낸다.** 방위사업청 부품국산화(상생협력형) 공고는 개발 대상에 "단종이 되었거나 단종이 예상되는 품목"을 넣고, 정부와 투자기업이 1:1로 내며 중소기업이 25% 이상을 부담한다(K2) [원문 확인]. 다만 이 돈은 부품 개발비이고, 대체 판정 도구 구매비로 인정되는지는 확인하지 못했다.

**판단**: 도구 시장과 가격대가 있다는 근거는 강하다. 쓰는 사람은 설계·부품 엔지니어이고 결재는 구매·공급망 조직 쪽이라는 근거는 약~중이다(벤더 자료와 익명 일화가 대부분이고 1인칭 결재 증언은 없다). 한국 민간 중소 제조사가 실제로 돈을 낸다는 근거는 찾지 못했다. 그래서 H2-A는 "설계 엔지니어가 쓰고 구매·공급망 조직이 결재하는 회사 단위 연 구독"으로 좁혀 가설로 두고, 첫 유료 고객 후보로 방산 부품 업체를 추가한다. 남은 확인은 같은 파일 4절의 인터뷰 질문 5개다.

---

## 3. 목표 사용자 페르소나와 반복 문서 업무

### 3-1. 페르소나 정의

| 항목 | 페르소나 A — 주 사용자 (탐색·검토자) | 페르소나 B — 승인·의사결정자 (책임자) |
|---|---|---|
| 역할 | 소형 MCU·임베디드 보드 하드웨어 개발자 (경력 1~4년, 소규모 HW팀 또는 메이커/스타트업) | 하드웨어 팀 리드 / 연구소 파트장 (BOM 승인·시제품 발주 책임) |
| 반복 문서 업무 | 기존 KiCad 보드의 다이오드가 단종·재고 부족·패키지 변경·원가 절감 대상이 될 때마다, 회로도/넷리스트에서 역할을 확인하고 후보 데이터시트 PDF 3~10개의 정격표·특성곡선·각주·패키지 치수를 대조해 대체 가능 품번을 추린다 | 개발자가 올린 대체 부품 후보와 견적서를 보고, ① 원래 회로 역할에 비춰 전압·전류·속도 여유율이 충분한지, ② 데이터시트 시험 조건이 실제 보드 조건과 맞는지, ③ 패드(풋프린트) 수정이 필요한지 확인한 뒤 발주·견적 저장을 승인한다 |
| 현재 해결 방법 | 유통사(Mouser/DigiKey) 필터에서 원래 부품과 전압·전류가 같거나 높은 부품을 검색한 뒤, PDF를 하나씩 열어 `Ctrl+F`로 `VRRM`, `VF`, `trr`, `VZ`를 찾고 엑셀/메모장에 수기로 비교표를 만든다 | 개발자가 구두나 메신저로 가져온 품번의 데이터시트 PDF를 다시 열어 1~2쪽 정격표와 패키지 도면을 눈으로 재확인한다 |
| 핵심 불편 (Pain Point) | ① 원래 부품이 과사양(`5V` 회로에 `1000V 1N4007`)이면 사양 필터만으로는 더 작고 적합한 후보를 못 찾음<br>② 한 PDF에 `1N5817/1N5818/1N5819`나 `BZT52C2V4~C39`가 함께 들어 있어 행·열을 잘못 읽거나 `TYP` 값을 `MAX` 보장값으로 착각하기 쉬움<br>③ 범용 챗봇(Codex 50문항 측정)은 데이터시트 출처(쪽·표·행) 없이 결론만 내고, 조건을 확인하지 못한 값을 단정하거나 넷리스트 없이 연결을 추정함(오답 4건 · 과잉 거절 1건. 후보 찾기 5건이 낸 품번은 모두 정답 집합 안이라 없는 품번을 지어낸 건은 없었다. [EVAL_REPORT.md](../../EVAL_REPORT.md) 10장, [TALLY.md](../../evals/results/graph/2026-11-12-codex-v3-50/TALLY.md)) | ① 개발자가 어떤 데이터시트 몇 쪽·어느 표 행을 근거로 판정했는지 추적하기 어려움<br>② 온도 조건(`TA=25°C` 대 `TJ=25°C`)이나 미확인 조건(`USB D+/D-` 정전용량 등)이 빠진 채 "대체 가능"으로 올라오면 시제품 불량으로 이어짐 |
| SojaFit에 기대하는 것 | 넷리스트와 대상 부품(`D1`)만 지정하면 회로 연결에서 역할과 필수 조건을 도출하고, 코퍼스 데이터시트의 정확한 쪽·표·행을 인용해 후보별 판정 5종을 내주며, 조건이 부족하면 억지 추천 대신 무엇이 부족한지 알려 주는 것 | 판정마다 인용된 데이터시트 쪽·표·행과 결정적 수치 비교 결과를 한눈에 검수하고, 내가 판정 결과를 승인한 뒤 견적을 DB에 저장·이력화하는 것 |

---

## 4. 고객 여정 맵 (Customer Journey Map)

교안의 단순 노드 흐름(User Flow)과 구분하여, 사용자가 부품 변경 문제에 부딪혀 최종 견적을 승인하기까지 겪는 6단계의 행동, 접점, 불편(Pain Point), 위험, SojaFit의 개입과 설계 근거를 정리한다.

| 단계 | 1. 문제 발생 (단종·수급·변경) | 2. 회로 역할 파악 | 3. 대체 필수 조건 설정 | 4. 후보 탐색 및 데이터시트 대조 | 5. 대체 적합성 판정 및 리스크 확인 | 6. 견적서 검토·승인 및 이력 재사용 |
|---|---|---|---|---|---|---|
| 사용자 행동 | BOM 점검 중 특정 다이오드(`D1`, `D2`, `D3`)의 재고 소진·단종·크기 축소 필요를 발견함 | KiCad 회로도와 넷리스트(`.net`)를 열어 해당 다이오드의 애노드(A)·캐소드(K)가 어느 넷(`VCC`, `GND`, `USB D-`, 코일 등)에 연결됐는지 추적함 | 역할(역극성 보호, 플라이백, 제너 클램프, 고속 스위칭)에 따라 필요한 `VRRM`, `IF`, `VF`, `VZ`, `trr`, `CJ`와 여유율을 정함 | 후보 품번 데이터시트 PDF 여러 개를 내려받아 `ABSOLUTE MAXIMUM RATINGS`, `ELECTRICAL CHARACTERISTICS`, `ORDERING INFORMATION`, 외형 치수 표를 대조함 | 후보가 원래 품번과 동일품인지, 사양 동등인지, 사양은 낮아도 회로 역할상 충분한지, 기판 수정이 필요한지 결론을 냄 | 선정 근거와 수량·단가를 묶어 팀 리드에게 공유하고, 승인된 대체안만 BOM·견적 이력으로 남김 |
| 접점 (Touchpoint) | BOM 시트, 유통사 재고 알림 | KiCad 회로도, `.net` 넷리스트, `connections.json` | 설계 가이드, 엔지니어 경험, 이전 프로젝트 메모 | 제조사(TSC 등) 데이터시트 PDF, 유통사 검색창, 범용 챗봇 | 엑셀 비교표, 데이터시트 각주·특성 곡선 | 팀 메신저/리뷰 회의, 견적서 양식 |
| 현재 방식의 Pain Point | 당장 대체 가능한 후보가 사내에 있는지, 어디서부터 찾아야 할지 막막함 | 오픈소스·외부 레퍼런스 보드는 왜 그 다이오드를 썼는지 주석이 없어, 원래 품번(`1N4007` 1000V 등)의 사양을 무조건 따라가게 됨 | 역할에 맞는 여유율 기준이 사람마다 다르고, 주변 온도(`TA`)·펄스 폭·신호선 정전용량 같은 숨은 조건을 빠뜨림 | ① 한 PDF 안의 형제 품번 행(`1N5817` 대 `1N5819`) 혼동<br>② `TYP` 값과 `MAX` 보장값 혼동<br>③ 개정판(`G1804` 대 `G2611`)·주문코드(`H` = AEC-Q101) 차이 누락 | 범용 챗봇은 없는 품번을 추천하거나 조건이 부족해도 "가능하다"고 단정함. 반대로 유통사 사양 필터는 5V 회로의 1000V 다이오드 대체품으로 또 1000V만 찾아줌 | 근거 페이지·표가 기록되지 않아 승인자가 데이터시트를 처음부터 다시 읽어야 하고, 승인 전 초안이 확정본과 섞임 |
| 실패 시 위험 | 일정 지연 | 역할 오판(제너 클램프를 일반 정류기로 오인 등) | 과사양 고착 또는 정격 부족으로 인한 소자 소손 | 잘못된 표 행·전형값 인용으로 인한 시제품 동작 불량 | 스루홀(`DO-35`)과 표면실장(`SOD-123F`) 패키지 차이를 놓쳐 보드 조립 불가 | 미승인 견적·오판정 사례가 다음 보드 설계에 그대로 재사용됨 |
| SojaFit의 개입 (해결 방식) | 로그인 후 회로 넷리스트와 대상 부품(`D1`) 및 질문 입력(`POST /api/auth/login`, 그래프 `입력 읽기`) | `입력 읽기`가 `connections.json`에서 대상 부품의 값·풋프린트와 전원 경로(예: `J1 → S1 → D1 → F1 → RAW`)를 여러 단계 따라 코드로 추출해 `[넷리스트]` 근거로 제공(LLM 미사용, `SPEC.md` 2절 그래프 표) | 회로 역할 설명과 역할별 필수 조건 규칙(`SPEC.md` 2·5절)을 분리하고, 빠진 회로 값은 판정 길의 `interrupt`로 한 번 되묻는다(`SPEC.md` 2절). 조건이 끝내 부족하면 `NOT_VERIFIED`로 분류 | `품번·판 확인`이 품번·개정 코드를 코퍼스 목록과 코드로 대조하고, `Supervisor`가 계획을 세운 뒤 `RAG 에이전트`가 하이브리드 검색을 하며 형제 품번 행·타 개정판을 LLM 전에 코드로 거른다(`other_part_row`, `backend/multi_agent/agents/docs.py:111`). 문서 할 일 하나의 검색은 최대 2회(`backend/multi_agent/contracts.py:19`) | 수치·단위 비교는 `Spec 에이전트`가 `backend/judge/` 코드로만 수행한다. 판정 답은 `답 정리`에서 코드 틀(`render_judgement`, `backend/multi_agent/messages.py`)이 판정 5종(`IDENTICAL` / `SPEC_EQUIVALENT` / `ROLE_SUFFICIENT` / `NOT_SUFFICIENT` / `NOT_VERIFIED`), 조건 표, 인용, 빠진 값으로 만들고 LLM이 숫자를 다시 쓰지 않는다. 판정 답에 "같은 동작은 보장하지 않습니다" 고지가 붙는다(`backend/multi_agent/messages.py:51,110`) | 완료 판정에서 승인 가능한 후보를 별도 승인 API로 승인하면 사용자별 승인 사례를 저장하고, 승인 ID로 가격 없는 견적을 저장한다. 견적 저장 전 승인은 그래프 `interrupt`가 아니라 API 단계다(`SPEC.md` 2절). 승인 사례는 새 분석의 모델 입력에 넣지 않는다(`SPEC.md` 8.5). |

---

## 5. 범용 챗봇과 동일 질문 5개 비교

### 5-1. 비교 항목

범용 챗봇(코퍼스·넷리스트 검증 경계가 없는 일반 LLM 응답)과 SojaFit에 동일한 질문 5개를 넣어 아래 4가지를 비교한다.

1. 근거 인용의 검증 가능성: 데이터시트 파일명·개정코드·쪽·표·행 또는 넷리스트 연결 경로를 인용하는가, 인용 번호가 실제 검색 청크에 존재하는지 코드로 검증하는가.
2. 형제 품번·시험 조건·보장값(`MAX` 대 `TYP`) 구분: 한 데이터시트 안의 다른 품번 행이나 전형값을 보장 최댓값으로 섞어 쓰지 않는가.
3. 확인 안 됨(`NOT_VERIFIED`)과 거절 처리: 사용자 동작 조건이 부족하거나, 문서에 보장 최댓값이 없거나, 코퍼스에 없는 품번일 때 억지 추측 대신 멈추는가.
4. 역할 기반 대체 판정: 원래 부품보다 정격 숫자가 낮아도 회로 사용 조건에서 역할상 충분(`ROLE_SUFFICIENT`)한 후보를 근거와 함께 판정할 수 있는가.

### 5-2. 비교한 질문과 결과

비교 대상은 범용 코딩 에이전트 Codex다. 질문 5개는 동결 v3의 v3-01, v3-05, v3-10, v3-26, v3-45이고, 질문 요약, 판정 기준, 두 답변, 차이는 [EVAL_REPORT.md](../../EVAL_REPORT.md) 10장 표가 정본이다. Codex 입력은 [evals/guides/v3_50_codex_paste.md](../../evals/guides/v3_50_codex_paste.md), 답변 전문은 [evals/results/graph/2026-11-12-codex-v3-50/codex_answers.md](../../evals/results/graph/2026-11-12-codex-v3-50/codex_answers.md)에 있다. 판정 기준은 [동결 v3 정답](../../evals/dataset_v3.jsonl)의 `expected`를 따르며 두 답변의 자동 채점 결과가 아니다.

판정 출처 (비교 대상, 정답 작성, 판정자의 기재):

v3 정답 초안은 Codex가 작성했고 판정자는 1차 심태현·최종 하정운이다(정본: [EVAL_REPORT.md](../../EVAL_REPORT.md) 2절 평가셋 표). 작업 원본은 저장소 밖에 있으며, 비교 대상도 Codex이므로 결과 해석에서 이를 고려한다. v1은 [작업 기록](../worklog/jeongun.md)에 Codex 세션 사용이 명시돼 있다.

---

## 6. 외부 검토 1명 점검 계획 및 기록 양식 (E1-5)

외부 검토는 아직 수행하지 않았고 기록이 없다. 검토자는 전자·하드웨어 경험자 또는 타 조·현업 개발자 1명으로 하고, 검토자 정보는 실명 대신 역할·경력으로 적는다.

| 항목 | 내용 |
|---|---|
| 검토 시나리오 | 정상 판정 1건(`e03` 또는 `draftv2-n03`), 조건 부족 또는 보장값 부재 거절 1건(`n01` 또는 `n14`), 승인 대기 1건 |
| 질문 1 | 인용된 데이터시트 쪽·표·행만으로 판정을 신뢰할 수 있는가 |
| 질문 2 | `NOT_VERIFIED`로 멈추는 경계가 실무에서 납득되는가, 너무 잦은가 |
| 질문 3 | 지불 주체 가설(개발팀 구독 대 유통사 제공) 중 어느 쪽이 현실적인가 |
| 남은 일 | 검토 수행, 의견과 반영 여부(반영 커밋 또는 제외 사유) 기록 |

---

## 7. 서비스의 약점과 한계

서비스의 약점은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 11장이 정본이고, 검색 실패 유형은 같은 문서 3-1·5장에 있다. 현재 서비스의 그래프 구조는 [SPEC.md](../../SPEC.md) 2절 "그래프"를 따른다.

| 항목 | 상태 | 근거 |
|---|---|---|
| 외부 검토 1명 | 미수행 | 6절 |
| 지불 주체 가설 H1, H2-A, H2-B, H2-C | 미검증 | 2-2절 |
| 각주 [3] 대체재 조사 파일 | 저장소에 있다(2026-11-13 이관): [candidate-g-market-saturation.md](evidence/candidate-g-market-saturation.md), [candidate-circuit-role-substitution.md](evidence/candidate-circuit-role-substitution.md). 2-1절 4번의 근거 | [evidence/EVIDENCE.md](evidence/EVIDENCE.md) |
