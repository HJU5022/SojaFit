# jaehun 작업 기록

## 2026-11-02 PR #23과 저장 경로 정합성 조정

- 요청: PR #23을 고려해 수정하되 코퍼스 축소 도구는 남기고 적용하지 않는다. 원본 13분류 전체를 유지한다.
- 코드: 수동 halfvec SQL은 HNSW를 제거하고 재생성하지 않는다. ingest는 인덱스가 있는 경우에만 재색인한다. halfvec 검색·API 없는 비교는 저장값을 float32로 읽고 질문 float32를 보존한다. subset CLI는 서비스·초기화·적재에 연결하지 않았으며 실행하지 않았다. 기본 vector와 원본 캐시를 유지한다.
- 문서: SPEC §6, RAG/DB 지도·ERD·표 정의, 저장 작업서와 사전 등록에 원본 유지·축소 적용 보류·변경된 거리 조건을 명시했다. #9·#10의 최초 기대와 합성 기록은 보존한다. 평가 ADR 0005를 0008로 옮겨 PR #23의 0005~0007과 번호 중복을 해소하고 지도·0003 링크를 갱신했다.
- 검증: 전용 임시 PostgreSQL(pgvector 0.8.6), 새 테스트의 실패 2건(HNSW 존재·질문 반올림으로 잘못된 1위)을 먼저 확인했다. 수정 후 storage 9 passed, `TEST_DATABASE_URL=<전용 로컬 DB> uv run python -m pytest -q`는 60 passed, 1 skipped(실제 코퍼스 BM25). SQL 반복·행 보존·HNSW 없는 API 0회 재적재·float32 경계 순위를 확인했다. `git diff --check` 통과.
- 독립 AI 검토: 중요한 코드 문제 추가 없음. psql이 DATABASE_URL을 자동으로 읽지 않는 절차 오류를 지적받아 명시적 접속 인자와 ON_ERROR_STOP을 추가했다. 검토자도 storage 9개 통과를 별도로 확인했다. 사람 승인을 대신하지 않는다.
- 병합 확인: PR #23 head df9f42d와 작업 트리의 `git stash create` 객체를 `git merge-tree --write-tree`로 가상 병합해 exit 0을 확인했다. 실제 브랜치/PR 병합은 하지 않았다.
- 확인 못 한 것: 전체 원본 DB/카드/벡터 미확보로 실제 전체 용량·237.8MiB·1,000개 순위·공식 Recall/MRR은 미측정이다. 동일 본문 벡터 중복 제거 구현도 이번 범위 밖이다. 평가셋·동결 파일·원격 DB는 변경하지 않았다.
- 외부 전달문은 proj3-b-handoff/review-20261102/discord-message.md에서 갱신한다. 이번 후속 변경은 로컬 검토용이며 푸시·PR 수정·Discord 전송은 하지 않는다. 이전 원격 생성 예외를 확대하지 않는다.


## 2026-11-02 원본 halfvec 환경 재현과 별도 재검수 착수

- 사용자 방향: 기존 코퍼스를 그대로 재현한 뒤 별도 검수. 분류별 축소를 원본 방식의 재현으로 간주하지 않는다.
- 확인한 근거: origin/main은 4a74b70으로 유지된다. PR #23 df9f42d의 SPEC·ADR·jeongun 기록은 문서 변경뿐이며 실험 실행 코드·데이터를 포함하지 않는다. 보고 경로는 원본 전체 → HNSW 제거 → halfvec → 같은 본문 벡터 중복 제거, 코퍼스 합계 MiB는 829.5→466.7→258.0→237.8이다. 실제 질문 임베딩 비교·Supabase 서버 시간은 그 기록에서도 미확인이다.
- 원본 탐색: 동일 저장소 Releases 0개, Actions 산출물 0개, 공유 Notion D0~D1에는 원래 수집·파싱 절차만 있고 카드·벡터 다운로드는 없다. 로컬 예상 corpus/SojaFit 경로와 전달 ZIP에도 원본 벡터가 없으며, 연결 Drive의 프로젝트 검색에서 관련 자료를 찾지 못했다. 비연결·다른 사용자 자료까지 없다는 뜻은 아니다.
- 실제 재검수: 52문항의 NET 해시, 관련 gold PDF 6개의 실제 파일 SHA256이 현재 manifest와 모두 일치했다. 전체 DB·237.8MiB·1,000개 순위 동일성은 재현하지 못했다. API 재호출 0, 원본·평가셋·원격 PR 변경 없음.
- 결과 위치: 저장소 밖 proj3-b-handoff/reproduction-20261102/preflight.json 및 reproduction-review.md에 확인 범위·원본 확보 후 단계별 검사·필수 자료를 기록했다. 아직 보내지 않은 discord-message.md는 원본 복원용 자료 요청 중심으로 수정하고 이전 버전을 별도 보존했다.
- 현재 막힌 조건: 변환 전 DB 덤프 또는 chunks.jsonl+원본 vectors.f32·vectors.sha.txt와 실제 실험 SQL/스크립트, 동일 표본·설정이 없다. Supabase 비밀번호 없이도 이 묶음으로 로컬 재현할 수 있다. 기존 합성 데이터 시험을 원본 검수 결과로 대체하지 않는다.
- 다음: 위 자료를 확보하면 원본 해시·모델·dtype을 고정하고 빈 로컬 DB에 API 없이 복원, 같은 SQL로 단계별 용량/순위 재현, 평가셋 근거·검색 검수를 별도 결과로 남긴다. Draft PR #24의 저장 도구 부분은 원본 방식 확인 후 정리 대상으로 둔다.

## 2026-11-02 사용자 명시적 예외 요청에 따른 Draft PR 게시

- 사용자 지시: 조장 허락이 없고 Draft도 원격 쓰기에 해당한다는 안내 후 사용자가 "그냥 만들어"라고 명시했다. 이번 지시는 jaehun 푸시·Draft PR 생성에 대한 예외로 적용하며, 조장 허락을 받았다고 기록하지 않는다.
- 적용 범위: 검증한 현재 변경과 이 작업 기록만 게시. 강제 푸시·리뷰어 지정·Ready 전환·머지·Discord 직접 게시 없음. AGENTS.md 자체는 변경하지 않는다.
- 대신 한 확인: 최신 main 통합, 독립 AI 재검토, 59 passed/1 skipped, Gitleaks 탐지 없음, 원본 평가셋 보존·32개 범위 파일 확인. 팀원의 PR 승인은 아직 받지 않았다. 실제 코퍼스 250MB·품질과 검수 대기 문항은 미완료로 유지한다.

## 2026-11-02 PR 전 재검토·최신 main 통합·전달문 준비

- 한 일: 독립 재검토 후 추가 두 문항의 human_2 O와 작업서의 빈 검수란 설명 불일치를 고쳤다. 최신 origin/main 4a74b70(기존 HEAD보다 7커밋 뒤)을 받았고, 작업 파일 32개만 지정해 stash 보관한 뒤 fast-forward·apply로 복원했다. 미추적 넷리스트.zip은 제외·보존했다. ingest 충돌은 DOC_DEFAULTS와 halfvec/cache-only를 모두 유지해 해결했다.
- 최신 main 호환: manifest에서 path가 빠진 새 형식에 맞춰 subset이 source_url의 파일명(URL query 제거·%20 복원)도 읽게 고쳤다. TDD 1 failed/23 passed → 24 passed. 기존 path 입력도 보존했다. 1,360문서의 PDF 해시·ID·개정판·쪽·카드 수·글자 수가 이전 manifest와 동일함을 대조했다. 새 DB 초기화 이름 000_init.sql로 안내를 맞추고 DB 지도에 있던 중복 파일 행을 정리했다.
- 실행과 결과: 전용 임시 PostgreSQL에 000_init.sql을 적용한 뒤 `TEST_DATABASE_URL=<전용 localhost DB> uv run python -m pytest -q` → **59 passed, 1 skipped**. skip은 실제 코퍼스 DB가 필요한 BM25 시험이다. 첫 새 컨테이너 실행은 초기 확장 미설치로 ingest 시험 1건이 실패했고 초기화 후 통과했다. 코드 결함으로 포장하지 않는다.
- 재검토: 새 독립 AI 검토에서 중요한 결함 없음. 최신 main 통합 후 subset·DOC_DEFAULTS·COPY·문서도 재확인했다. 52건·26/26·검수 40/7/5, 기존 질문·입력·NET 보존, v1/FROZEN 미변경, 로컬 링크 및 git diff --check 통과.
- 비밀값 확인: Gitleaks v8.30.1로 승인 범위 32개 파일(약 552KB)을 별도 사본에서 redacted 검사, no leaks found. `.env`, ZIP, 전체 코퍼스, PR/Discord 전달문은 PR에서 제외한다. 기존 pyproject.toml·uv.lock은 변경하지 않았다.
- 정리: 평가 검수/분류와 저장 용량 검증 도구를 논리 단위 커밋으로 나눈다. PR 본문·Discord 복사용 전달문·검사 보고서는 저장소 밖 `/home/honorbear/proj3-b-handoff/review-20261102/`에 둔다. 실제 250MB/검색 품질·대상 Supabase 버전·검수 보류 5건은 미완료로 표시한다.
- 원격 권한: AGENTS.md 팀 규칙 1의 이번 대화 조장 허락이 확인되기 전에는 push·PR 생성·리뷰어 지정을 하지 않는다. 로컬 커밋과 검토 가능한 PR 본문까지 준비한다. Discord는 직접 게시하지 않고 사용자 복사문만 만든다.

## 2026-11-02 코퍼스 250MB·halfvec 도구와 로컬 검증

- 승인 범위: 사용자 요청 1~3번. 전체 DB 250,000,000B 이하 우선, 평가의 회로 5종 유지. 질문 재작성·원격 게시·원본 삭제는 수행하지 않는다.
- 근거: 공유 Notion D0~D1 페이지를 읽었다. 현재 500만은 문서 건수가 아니라 약 500만 글자이고 카드는 52,244장이다. 사용자는 837MB가 다른 사람 환경의 보고치라고 확인했다. 이쪽에는 적재 DB·전체 카드·카탈로그·벡터가 없다. .env·DATABASE_URL 없음, 현재 compose DB 없음, 연결된 Supabase에도 SojaFit 프로젝트 없음.
- 사전 기록: 실제 모델 호출·전체 코퍼스 실험 예산 $0, 공식 평가 실행 없음. PREREGISTER #9는 정밀도만, #10은 코퍼스 분류만 바꾸며 실제 결과는 미측정이다. 읽기 전용 비교 최대 1,000개·기본 120초, query당 최대 5초. 표본·후보 부족과 timeout은 미통과.
- 구현 순서: 사람 합의 40건 변경 보류·숫자형 7건·보류 5건 구분 → 분류별 별도 사본 도구 → halfvec 수동 전환·타입 일치 적재/검색 → 실제 PostgreSQL 계약 시험 → 원시 결과·문서·독립 검토.
- 계약 시험: 이미 있던 pgvector/pgvector:pg16 이미지로 전용 임시 컨테이너 sojafit-halfvec-check-1102를 만들었다. localhost 임의 포트만 노출하고 tmpfs 저장을 사용한다. 원본·다른 DB는 건드리지 않는다. 합성 데이터의 SQL·정밀도·COPY·질의 시험이며, 실제 52,244개 검색 품질을 입증하지 않는다.
- 시험 전 기록: TDD에서 test_rag_storage는 storage 모듈 미구현 ImportError로 먼저 실패했다. 분류 도구는 별도 에이전트가 모듈 부재 8실패 뒤 구현했으며 duplicate idx·payload 카드 수 회귀도 실패를 확인한 뒤 수정했다.
- 바꾼 파일: backend/rag/subset.py·storage.py·ingest.py·retrieve.py·RAG.md, db/halfvec.sql.manual·DB.md·ERD.md·table-definition.md, tests/test_rag_subset.py·test_rag_storage.py·TESTS.md, .env.example, SPEC.md, EVAL_REPORT.md, evals/EVALS.md·PREREGISTER.md·DRAFT_50_REVIEW.md·draft_50.jsonl·results/storage_contract_2026-11-02.json, docs/specs/corpus-storage-budget.md·SPECS.md·rag-pipeline.md, 이 파일.
- 검수 표시 결과: 기존 40건에 실제 사람 O를 동기화하고 현재 코퍼스 기준 변경 보류로 표시했다. 숫자형 7건은 기계 대조만 있는 기록으로, 변경·추가 5건은 재검수/1차 판정 대기로 구분했다. 52건의 질문·정답·분류·근거는 이 표시 작업에서 바꾸지 않았고 v1·FROZEN도 보존했다.
- 실제 로컬 계약 결과: pgvector 0.8.6, 합성 64행·1536차원에서 vector→halfvec 후 64행 유지, 평균 pg_column_size 6148→3076B. 16개 합성 질의 비교는 실제 벡터 1,000개 게이트가 아니다. 결과는 evals/results/storage_contract_2026-11-02.json이며 250MB/실제 검색 품질 달성은 null·false로 구분했다.
- 실행과 결과: `TEST_DATABASE_URL=<전용 localhost 시험 DB> uv run python -m pytest -q` → **53 passed, 1 skipped**. 건너뛴 것은 실제 코퍼스 DB의 BM25 시험이다. DB 관련 시험은 임시 스키마를 만들어 제거했다. CLI help와 git diff --check 통과, pyproject.toml·uv.lock 변경 없음. uv sync로 기존 lock 환경만 설치했다.
- 독립 검토·수정: 분류 도구의 고유 본문 수 기준 payload 추정이 실제 카드당 DB 행을 과소 계산하는 점을 바로잡았다. 누락된 manifest.chunks·중복/불연속 idx는 실패 처리했다. 비교의 초기 메타데이터/ID 조회까지 시간 제한을 확장하고 호출자 SET LOCAL 설정을 rollback으로 복구했다. 잠금 회귀·설정 보존 회귀를 실패 확인 후 통과시켰다. 최종 검토에서 남은 중요한 문제 없음; cache-only 검토도 6 tests passed.
- API 금지 경로: 새 subset은 빈 DB에 적재해야 한다. 전체 DB에 ingest를 반복해도 삭제되지 않으므로 축소라고 하지 않는다. 캐시 복사본과 --cache-only를 사용하면 벡터 누락 시 provider를 부르기 전에 실패하고 DB 트랜잭션은 rollback된다.
- 확인 못 한 것: 실제 catalog·전체 카드·float32 벡터·DB 덤프가 없어 실제 축소 사본 생성, G3(50문서/1만 고유본문), 전체 DB 250MB, 실제 1,000개 순위 겹침, 동결셋 Recall@5·MRR을 재지 못했다. 대상 Supabase의 pgvector 버전·메모리·속도도 미확인이다. 기본 vector는 유지했다. 전용 임시 컨테이너 sojafit-halfvec-check-1102는 확인 후 제거했다. 원격 변경·게시·커밋은 하지 않았다.
- 다음: 실제 자료를 확보하면 작업서의 새 출력 폴더·빈 DB·캐시 사본 명령으로 #10과 #9를 별개 실행한다. 품질 최종 채택은 동결 후 동일 코퍼스 Recall@5·MRR 무하락과 전체 DB 실측으로 정한다.

## 2026-11-02 추가 두 문항의 재훈 O 반영

- 한 일: 사용자 승인에 따라 n21·n22의 재훈 확인란과 JSONL human_2에 O·확인일(2026-11-02)을 기록했다. 두 건의 상태는 1차 사람 검수 대기로 명시했다.
- 바꾼 파일: evals/DRAFT_50_REVIEW.md, evals/draft_50.jsonl, evals/EVALS.md, 이 파일.
- 확인: 변경 전후 대조에서 JSONL은 n21·n22의 human_2·상태·검수 경고만 바뀌고 정답·분류·근거·1차 판정 및 나머지 50행은 동일했다. 검토표와 JSONL의 O·날짜 일치, 52건·26/26 및 git diff --check를 확인했다. 이전 52건 검증 원시 결과는 2차 O 기록 전 스냅샷으로 보존했다.
- 확인 못 한 것: 하정운의 추가 두 건 1차 검수 및 변경 세 건의 재검수·합의. 평가 재측정·동결은 수행하지 않았다.
- 다음 할 일: 남은 사람 검수와 합의 후 전체 검수 기록 동기화·동결 전 검증을 수행한다.

## 2026-11-02 평가 분류 기준 반영과 52건 초안 확장

- 목적·범위: 사용자 승인에 따라 사용자 조건 부족(relevant + NOT_VERIFIED)과 핵심 문서 속성 부재(irrelevant / missing_attribute)를 구분하고 관련 2건을 추가한다. 모델 실험·새 코퍼스 수집·평가 실행·동결·원격 쓰기는 범위 밖이다.
- 한 일: EVALS.md와 SPEC §4에 기준을 기록했다. h03을 비관련, n01·n02를 NOT_VERIFIED로 현재 JSONL 초안에 반영하고 종전 정답·분류·근거·검수 메타데이터·1차 판정을 개정 이력에 보존했다. 변경된 답안의 1차 재검수·합의 대기를 명시했다.
- 추가 문항: n21은 1N5819의 온도별 역누설 전류, n22는 1N4148의 접합 정전용량. 정답·원문·대화 이력을 받지 않은 별도 AI가 질문을 먼저 작성하고, 주 에이전트가 PDF 표의 값·MAX/TYP·시험 조건과 manifest 해시를 대조했다. AI 역할 분리는 사람 독립 출제나 두 사람 검수의 증거가 아니다. 새 두 문항의 사람 확인란은 비어 있다.
- 바꾼 파일: SPEC.md, EVAL_REPORT.md, evals/EVALS.md, evals/draft_50.jsonl, evals/DRAFT_50_REVIEW.md, evals/results/draft52_validation_2026-11-02.json, docs/specs/evaluation-draft-52.md, docs/specs/SPECS.md, docs/adr/0003-평가셋-v1을-50건으로-동결.md, docs/adr/0005-평가-정보부족-구분과-52건-초안.md, docs/adr/ADR.md, 이 파일.
- 실행한 명령과 결과: `/tmp/sojafit-review-tools/uv run --no-project --with pypdf python /tmp/sojafit_validate52.py` → 고유 52건·26/26, 비관련 6/7/7/6, 기존 50건 ID·질문·input·source·target·가정 보존, 47행 바이트 동일, 세 변경 행의 이전 답안 복구 가능, 52건 NET 해시·대상 존재, 새 PDF 2개 manifest 해시 일치, 링크 대상 확인. `/tmp/sojafit-review-tools/uv run --no-project --with pytest python -m pytest tests/test_frozen_evals.py -q` → 1 passed. FROZEN.json 부재 상태이므로 동결 성공 증거는 아니다.
- 원문 확인: H2104 2쪽의 IR MAX 1mA(TJ25°C)·10mA(TJ100°C), PW30ms; K2301 2쪽 CJ MAX4pF, 1MHz·VR0V·기본 TA25°C를 화면과 텍스트로 확인했다. 추가 원본은 저장소에 넣지 않았다.
- 독립 검토: requesting-code-review 절차의 AI 검토에서 n01·n02의 옛 검수 메타데이터가 새 답안과 충돌하는 지적을 받았다. 원문 필드를 확인한 뒤 이전 메타데이터를 이력으로 옮기고 현재 필드를 새 기준에 맞췄다. 추가 두 문항의 사람 승인으로 취급하지 않았다.
- 문서 확인: git diff --check 통과. EVAL_REPORT의 11-01 점수는 변경 전 초안의 역사적 측정으로 남기고 52건 재측정으로 오해하지 않게 표시했다. 기존 파일명의 50은 유지해 링크를 보존했다.
- 확인 못 한 것: 변경 세 건의 1차 재검수·이견 합의, 추가 두 건의 두 사람 검수, 나머지 기존 사람 판정의 JSONL 동기화, 외부 전체 품번 목록·판정 기준표, 실제 답변·거절 채점기와 지표 분모. 52건 점수는 재측정하지 않았고 dataset_v1·동결 기록을 변경하지 않았다.
- 다음 할 일: 검토표에서 n21·n22를 확인하고 n01·n02·h03의 1차 재검수·합의를 받는다. 근거와 검수 기록 동기화 후 승격·동결·기준선 측정을 진행한다.

## 2026-11-02 n02 재훈 판정 재검토 반영

- 한 일: 사용자 동의에 따라 n02 재훈 확인을 O에서 X — NOT_VERIFIED로 변경했다. 차단 펄스 조건 미확인으로 불충족을 확정할 수 없다는 의견을 기록했다. 관련/비관련 분류는 사용자 조건 부족과 코퍼스 속성 부족의 구분을 합의할 때 정하도록 남겼다.
- 바꾼 파일: evals/DRAFT_50_REVIEW.md, 이 파일.
- 확인: 수정 전후 대조로 검토표의 n02 블록만 변경되었음을 확인하고 git diff --check를 실행했다.
- 확인 못 한 것: 1차 판정자와의 최종 합의 및 관련/비관련 정책. JSONL의 expected·kind·사람 판정 필드는 변경하지 않았다. 평가 재측정·동결은 수행하지 않았다.
- 다음 할 일: n01·n02·h03의 이견과 분류 기준을 합의한 뒤 최종 정답 및 JSONL 검수 기록에 반영한다.

## 2026-11-02 h03 재훈 분류 재검토 반영

- 한 일: 사용자 동의에 따라 h03 재훈 확인을 O에서 X — irrelevant / missing_attribute로 변경했다. VCC 최솟값의 근거가 없다는 이유와 n14와의 일관성을 기록했다. 최종 반영 시 관련 24·비관련 26이 되어 동결 전 구성 재검토가 필요함을 명시했다.
- 바꾼 파일: evals/DRAFT_50_REVIEW.md, 이 파일.
- 확인: 수정 전후 대조로 검토표의 h03 블록만 변경되었음을 확인하고 git diff --check를 실행했다.
- 확인 못 한 것: 1차 판정자와의 최종 합의. JSONL의 kind·expected·사람 판정 기록은 변경하지 않았다. 평가 재측정·동결은 수행하지 않았다.
- 다음 할 일: h03의 이견을 합의한 뒤 JSONL 검수 기록과 최종 분류를 반영하고 관련/비관련 구성 요건을 확인한다.

## 2026-11-02 n01 재훈 판정 재검토 반영

- 한 일: 사용자가 주어진 정보에 따르면 NOT_VERIFIED에 동의하여, n01의 재훈 확인을 기존 O에서 X — NOT_VERIFIED로 변경했다. TA 조건을 추가하지 않고 질문을 유지한다는 의견을 기록했다.
- 바꾼 파일: evals/DRAFT_50_REVIEW.md, 이 파일.
- 확인: 검토표에서 n01 블록에만 변경이 있는지 대조하고 git diff --check를 확인했다.
- 확인 못 한 것: 1차 판정자와의 최종 합의. JSONL의 expected·kind·사람 판정 필드는 이번에 변경하지 않았다. 평가 재측정·동결은 수행하지 않았다.
- 다음 할 일: n01의 이견을 합의한 뒤 최종 정답과 JSONL 검수 기록에 반영한다.

## 2026-11-02 사람 확인란에 세 문항 재검토 쟁점 기록

- 한 일: 사용자 요청으로 DRAFT_50_REVIEW.md의 h03·n01·n02 재훈 확인란 아래에 Codex가 지적한 쟁점을 덧붙였다. 기존 O는 보존하고 최종 결론 미확정인 재검토 메모로 표시했다.
- 바꾼 파일: evals/DRAFT_50_REVIEW.md, 이 파일.
- 확인: 수정 전후 대조로 검토표에 지정한 세 줄만 추가되었고 기존 내용이 동일함을 확인했다. git diff --check 통과.
- 확인 못 한 것: 세 쟁점의 최종 합의. 정답·분류·JSONL 판정 기록은 변경하지 않았고 평가 재측정·동결도 수행하지 않았다.
- 다음 할 일: 1차 판정자와 논의해 세 문항의 결론을 확정한다.

## 2026-11-02 요청 판본 확인의 후속 필요사항 기록

- 한 일: 평가셋의 사람 판정과 서비스의 자동 판본 확인을 구분하고, 미구현 요구를 기존 RAG 작업서에 기록했다. 보유 판본 대조, 연도 대응 근거, 코퍼스 부재와 실제 비존재의 구분을 명시했다.
- 바꾼 파일: docs/specs/rag-pipeline.md, evals/EVALS.md, 이 파일.
- 확인: 문서 내용과 기존 chunk.py의 개정 코드 추출·retrieve()의 품번 필터 계약을 대조했다. 로컬 링크·절 제목과 git diff --check를 확인했다.
- 확인 못 한 것: 자동 판본 판정의 동작과 평가 점수. 문서 기록만 했으며 모델 호출·평가 재측정·동결은 수행하지 않았다.
- 다음 할 일: 구현을 시작할 때 담당·입출력·필터·확인 불가 처리·테스트 기준을 확정한다. 외부 존재 조회의 도입 여부는 별도로 정한다.

## 2026-11-02 최신 main 반영과 50건 동결 전 보조 검증

- 한 일: origin/main c02d3ef를 jaehun에 fast-forward. 50건 구조·NET SHA256·대상 존재 확인, 인용 PDF 6개 SHA256·주요 행과 시험 조건 대조. n06의 D3.C 인용 VCC→5V 정정. 사람 판정과 동결 상태는 보존.
- 바꾼 파일: evals/draft_50.jsonl, evals/DRAFT_50_REVIEW.md, evals/SECOND_PASS_50_REVIEW.md, evals/EVALS.md, evals/results/draft50_second_pass_2026-11-02.json, docs/worklog/WORKLOG.md, 이 파일.
- 실행한 명령과 결과: git fetch origin main → HEAD...origin/main 0/33; git merge --ff-only origin/main → c02d3ef, HEAD=origin/main. git push·PR·API 쓰기 없음.
- 실행 환경: PATH에 uv가 없어 공식 설치 스크립트로 /tmp/sojafit-review-tools에만 설치. /tmp/sojafit-review-tools/uv run --no-project --with pypdf --with pytest python /tmp/sojafit_review50.py → 50건 구조·NET·대상, PDF 6개 해시 일치. /tmp/sojafit-review-tools/uv run --no-project --with pymupdf python 으로 G1804 5쪽·G2606 3쪽 임시 렌더링 후 화면 확인. 저장소 의존성 파일 변경 없음.
- 확인 명령: /tmp/sojafit-review-tools/uv run --no-project --with pytest python -m pytest tests/test_frozen_evals.py -q → 1 passed. FROZEN.json 부재 상태라 실제 동결 파일 검사는 수행되지 않음.
- 예산·측정: 모델 호출 0, 전체 검색/답변 평가·긴 빌드 실행 없음. PDF 3개만 제조사에서 임시 다운로드, manifest 해시로 고정. 원시 결과에 입력·manifest 해시와 PDF 해시를 기록.
- 확인 못 한 것: 실제 김재훈 2차 사람 판정, 전체 parts 색인, 외부 판정 기준표, 전체 외부 코퍼스·DB. n01(TJ/TA)·n02(서지 파형 조건)의 판정 합의. 검색 점수·답변 품질·실제 회로 동작은 측정하지 않음.
- 다음 할 일: SECOND_PASS_50_REVIEW.md의 미확인 근거와 n01/n02 판정을 합의하고 실제 사람 2차 결과를 기록. 승격할 50건을 재검증한 다음 dataset_v1.jsonl 동결·해시 검사. 미추적 넷리스트.zip은 보존.
