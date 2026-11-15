# 넷리스트 없는 프로젝트와 대화별 회로 버전

- 상태: 현행(구현 작업서). 서버 쪽은 구현·반영됐다(SPEC 4절 `POST /api/projects/{id}/netlist`). 화면 부분의 파일 이름은 11-16 새 화면 교체 전 것이다
- 기준일: 2026-11-14(문서 안의 마지막 날짜)
- 기준 커밋: 기록 없음
- 정본 여부: 정본(빈 프로젝트 · 중복 확인 · 대화별 회로 버전의 계약). 경로 목록은 [SPEC.md](../../SPEC.md) 4절
- 관련 문서: [local-live-api.md](local-live-api.md), [frontend/src/SRC.md](../../frontend/src/SRC.md)
- 사용자 결정: 다른 넷리스트를 붙여도 같은 프로젝트 안에서 새 회로 버전·새 대화로 이어간다. 사이드바 압축은 시안만 제시하고 적용하지 않는다.

## Why
- 프로젝트를 먼저 만들고 대화에서 회로를 올리려는 사용자가 데모 전용 생성 API의 404와 미연동 첨부 전송 차단을 만난다.
- 기존 회로를 덮어쓰면 과거 대화·재개·판정의 회로가 달라진다. 파일 없는 생성 성공, 첨부 실패 시 초안 손실 0, 과거 회로 변동 0을 확인한다.

## Goal
- 이름만으로 프로젝트를 만들고 채팅에서 KiCad 파일을 처리한다.
- 프로젝트 안의 회로 버전을 보존하고 대화를 해당 버전에 고정한다.
- 유료 호출 없이 파싱·저장·선택·전송 경계와 기존 기록 복원을 검증한다.
- 제외: 임의 문서/PDF 첨부, 이전 대화의 회로 변경, 자동 부품 추측, 운영 DB 적용, 실제 모델 분석, 사이드바 실구현.

## What
- 파일 없는 생성 → 채팅에서 넷리스트 안내 → 파일과 선택적 질문 입력 → 파싱·새 버전 저장 → 새 대화 → 질문에 특정된 다이오드가 있으면 기존 분석 경로, 없으면 부품 선택과 질문 초안 유지.
- 이미 회로가 있는 대화의 첨부 → 같은 프로젝트의 새 버전·새 대화. 기존 질문/결과는 원래 버전으로 복원·재개된다.
- 파일만 전송해도 파싱/부품 선택까지 진행하며 모델은 호출하지 않는다. 잘못된 파일/용량/소유권/서버 실패는 초안·첨부 유지, 자동 재시도 없음.

## How

### 프로젝트 생성 중복 확인 (2026-11-14)
- 빈 생성·데모 복제·넷리스트 생성 모두 같은 소유자의 이름(앞뒤 공백 제거·대소문자 무시) 또는 최신 회로의 원본 SHA-256이 같으면 저장 전409 CONFLICT를 반환한다. 파일명은 비교하지 않으며 회로 의미/서식이 다른 파일까지 동일하다고 추정하지 않는다. 다른 사용자와 과거 버전은 비교 대상이 아니다.
- 공통 error/code/message/request_id를 유지하고 선택적 details.duplicates에 최대5개 {id,name,matches:[name|netlist]}만 제공한다. 원본·해시·다른 사용자 정보를 응답/로그에 노출하지 않는다. Cache-Control은 private,no-store다.
- 기존 POST /api/projects 및 /api/projects/upload에 allow_duplicate(bool, 기본false) 쿼리를 추가한다. 사용자별 생성 트랜잭션을 직렬화해 동시 생성도 확인한다. true는 경고 후 명시적인 새로 만들기 선택에만 사용하며 원래 프로젝트를 수정하지 않는다. 새 DB 구조/경로/유료 호출은 없다.
- 화면은 경고와 기존 프로젝트 열기/중복을 확인하고 새로 만들기를 제공한다. 이름·선택 파일을 유지하고 입력 변경/닫기/재열기에는 확인 상태를 해제한다. 파일 전송 API와 같은 프로젝트의 새 회로 버전 생성은 이번 중복 검사 범위가 아니다.
- POST /api/projects JSON {name, demo_id?:string}: demo_id 생략 시 빈 upload 프로젝트, 지정 시 기존 데모 모드 제약 유지. 빈 프로젝트는 circuits 행 없이 v0 스냅샷(parts/nets=[])을 만들며 원본 파일을 저장하지 않는다.
- POST /api/projects/{id}/netlist multipart file 한 개(.net·.txt, UTF-8 KiCad export, 비어 있지 않은 5MiB 이하): 인증·Origin·기존 메모리 수신 상한 재사용. 정규화 연결/해시/파서 버전만 저장하고 {project, thread_id} 반환. 새 버전과 새 대화 생성은 같은 트랜잭션이며 기존 대화는 변경하지 않는다.
- DB: project_circuit_versions에 프로젝트별 불변 버전 저장, circuits는 최신 버전, threads.circuit_version으로 버전 고정. 기존 회로/대화는 v1으로 backfill. 실행 시작·재개·회로 상세의 모든 읽기 경로가 버전 고정을 따른다. FK cascade·RLS/권한 회수 유지.
- GET /api/projects/{id}?thread_id=UUID로 소유 대화의 회로 상세 조회. 다른 프로젝트/사용자 대화는404. Project DTO에 circuit_version(없음0)을 포함한다.
- 프런트(11-14 옛 화면 기준)는 기존 api/projects·Workbench·Review·ChatPane·useConversation을 재사용했다. 새 화면은 `frontend/src/Workbench.tsx`의 첨부가 이 API를 부른다. 파일은 run 요청에 넣지 않고 위 파싱 API를 먼저 사용한다. 요청 중 중복 전송/분석 방지, 실패 시 원문 유지. 전송 성공 후 새 문맥으로 이동하며 원래 ref를 새 파일의 대상으로 추정하지 않는다.

## AC
- Given 같은 계정의 같은 이름 또는 같은 파일 내용, When 확인 없이 생성, Then409·추가 저장0·안전한 소유 프로젝트 후보만 제공한다. 다른 계정의 같은 이름/파일은201이다.
- Given 중복 경고, When 기존 프로젝트 열기, Then 기존 프로젝트로 이동하고 새 생성0. When 명시적으로 새로 만들기, Then allow_duplicate=true로 새 id를 생성하고 기존 데이터는 유지한다.
- Given 경고 후 입력 변경 또는 창 재열기, When 다시 생성, Then 이전 중복 허용을 재사용하지 않는다. 동시에 같은 계정이 생성하면 확인 없는 두 생성 중 하나만 저장한다.
- Given 운영 모드, When 이름만 생성, Then201과 빈 회로; demo_id 지정은 계속404.
- Given 빈 프로젝트, When 유효 파일만 전송, Then v1과 새 대화/부품 목록; 유료 실행0.
- Given v1 대화, When 다른 파일 첨부, Then v2 새 대화; v1 상세/재개는 v1 회로 유지.
- Given 파일과 D1 질문, When 처리 성공하고 D1이 새 회로의 다이오드, Then 새 대화에 기존 run 경로 한 번만 사용.
- Given 대상 불명/범위 밖, When 처리 성공, Then 부품 선택 안내와 질문 유지; run0.
- Given 실패/빈 파일/초과/중복 전송/소유권 위반, When 전송, Then 안전 오류·초안/파일 보존·기존 버전 변경0.
- Given 과거 대화 주소로 이동/새로고침, When 복원, Then 당시 버전의 대상·연결·판정 표시.

## 구현·검증 순서
- [x] backend/projects·api/projects: 빈 생성/기존 multipart 공통화와 버전 import API, 인증/크기/실패 회귀.
- [x] db 버전 SQL과 conversations repository/memory_service: 생성/시작/재개/조회 고정, 기존 기록 backfill·삭제 cascade·트랜잭션 회귀.
- [x] frontend api/projects·Workbench·Review·useConversation: 첨부를 import로 연결, 빈 프로젝트 채팅, 초안·실패·새 문맥 회귀.
- [x] 프런트 전체·타입/빌드·관련 백엔드·구조 검사. 로컬 테스트 DB에만 SQL 적용 후 브라우저에서 파일 없는 생성/파싱/새 대화/과거 버전 확인. 에이전트 모델/검색 실행0.
