# 격리한 로컬 실제 API 실행

- 상태: 현행. 로컬 실행·로그인·저장·실제 모델·외부 검색 응답 확인(2026-11-15). KiCad 미설치 이미지의 공식 PDF 회로도 수신·정격 분석 통합 검증 완료. 검증은 11-16 새 화면 교체 전 화면으로 했다
- 기준일: 2026-11-15
- 기준 커밋: 기록 없음(2026-11-15 통합 검증 환경 기준)
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 4절 API · 7절 데모). 로컬 실제 API 실행 방식의 상세
- 관련 문서: [frontend/FRONTEND.md](../../frontend/FRONTEND.md), [db/DB.md](../../db/DB.md), [netlist-conversation-versions.md](netlist-conversation-versions.md)

## Why
(2026-11-15 당시) 로컬 5173은 더미 화면이고 8000은 조회 전용 검증 서버여서 프로젝트 생성·실제 분석을 확인할 수 없다. 운영 DB에 연결하지 않고 정식 서비스 흐름을 확인해야 한다.

## Goal
- localhost:8010 한 출처에서 빌드한 화면과 backend.main:app 제공.
- DEMO_MODE=0, DEMO_REPLAY=0, THREADS_ENABLED=1. 운영 DB 접속·변경 0회.
- 로그인·프로젝트 생성·대화 저장을 별도 로컬 DB에서 확인한다. 실제 분석·외부 회로도 검색을 실행하면 공급자 호출과 과금이 발생할 수 있다.
- 로컬 API 이미지에는 KiCad를 설치하지 않고 KiCad renderer 컨테이너도 시작하지 않는다. 기존 정적 회로도와 공개 PDF·PNG·SVG 회로도 검색은 사용하며, KiCad 원본만 있는 결과는 변환하지 않는다.
- 제외: 배포·운영 데이터 복제·Google OAuth/메일 공급자 설정 변경·평가셋 재측정.

## What
- docker-compose.local.yml만 지정해 별도 프로젝트·DB 볼륨으로 시작한다. 기존 데모 Compose와 실행 중인 서버는 보존한다. 서비스 구성은 api, db, thread-setup이다. API는 thread-setup 완료 후 시작한다.
- .env.local은 무시되는 로컬 비밀 파일이며 필요한 공급자 키와 별도 로컬 세션/DB 비밀값만 넣는다. 운영 DATABASE_URL·AUTH_SECRET·계정·Google/SMTP/Langfuse 설정을 복사하지 않는다.
- 로컬 코퍼스와 기존 Voyage 캐시만 재사용한다. 필요한 벡터가 없으면 자동 생성하지 않고 부족한 수와 버전을 알린다.
- 이 PC의 초기 코퍼스는 로컬 r104 자료(1,360문서·56,382청크)와 캐시다. 원본 PDF 식별자는 저장소 manifest와 대조하고 `local-r104-cache-2026-11-13`으로 구분한다. 운영 문서의 v4h 51,967청크와 동일하다고 간주하지 않는다. 검색 대상 55,022청크에는 모두 캐시 벡터가 있으며 검색에서 제외되는 표지 1,360건은 임베딩을 만들지 않는다.
- 실제 질문·회로도 검색은 공급자 과금 가능성을 실행 전에 알린 뒤 수행한다. 설정 확인만으로 분석 성공이라고 보고하지 않는다.

## How
- 루트 Dockerfile로 현재 체크아웃을 빌드한다. api와 thread-setup의 DATABASE_URL은 Compose 내부 db의 local_app DB로 고정한다. DB 포트는 호스트에 공개하지 않고 API만 127.0.0.1:8010에 바인딩한다.
- DB 비밀번호는 URI에 삽입하지 않고 PGPASSWORD로 분리해 예약 문자가 있어도 DB 주소·연결 문자열이 바뀌지 않게 한다. MCP 하위 프로세스도 기존 환경 상속 경로를 사용한다.
- `docker compose --env-file .env.local -f docker-compose.local.yml up -d --build --wait --wait-timeout 120`
- API healthcheck가 준비될 때까지 기다린 뒤 로그인·저장 검증을 수행한다. 컨테이너의 Started 표시만으로 HTTP 준비를 판단하지 않는다.
- 로컬 비밀 파일에는 LOCAL_DB_PASSWORD, LOCAL_AUTH_SECRET과 OPENROUTER_API_KEY, VOYAGE_API_KEY, EXA_API_KEY를 둔다. 외부 회로도 검색을 사용할 때는 EXA_WEB_SEARCH_ENABLED=1도 설정한다. API의 핵심 실행 플래그와 AUTH_ORIGIN은 Compose에서 고정한다. DEMO_MODE=0, DEMO_REPLAY=0, THREADS_ENABLED=1, KICAD_RENDERER_URL=""을 로컬 Compose가 강제한다.
- 로컬 로그인 정보는 .env.local의 LOCAL_LOGIN_EMAIL/LOCAL_LOGIN_PASSWORD에만 보관한다. 이 PC의 초기 일반 계정은 기존 해시 함수를 사용해 테스트 DB에만 생성한다. 새 환경에서는 `docker compose --env-file .env.local -f docker-compose.local.yml exec api python -m backend.auth`로 대화형 계정을 만든다.
- 새 DB는 기존 db/*.sql과 backend.conversations.memory_service --setup으로 준비한다. 코퍼스는 기존 ingest의 --chunks-only로 넣고 해시가 일치하는 캐시 벡터/비트 코드를 검색 대상 행에만 COPY한다. --voyage는 표지까지 캐시가 있는 경우에만 쓸 수 있다. 적재 하위 프로세스의 공급자 키를 비우고 시작 과정에 유료 호출을 넣지 않는다.
- 초기 계정은 기존 backend.auth의 비밀번호 해시/계정 생성 경로를 사용해 테스트 DB에만 만든다. 데모 로그인·인증 우회는 추가하지 않는다.
- 로컬 이미지의 프런트 빌드에는 `VITE_LOCAL_ATTACHMENT_UI=1`을 넘긴다(`docker-compose.local.yml`, `Dockerfile` 빌드 인자). 11-16 새 화면의 소스는 `VITE_` 변수를 읽지 않아 이 값은 지금 효과가 없고 첨부 UI는 항상 보인다. 현재 실제 첨부 처리 계약은 [netlist-conversation-versions.md](netlist-conversation-versions.md)를 따른다. 파일 선택·드롭 후 전송하면 기존 파서로 검증하고 새 회로 버전·새 대화로 이어지며 실패 시 초안·첨부를 보존한다. 실제 API 분석과 외부 회로도 검색은 공급자 설정에 따라 과금된다. 업로드 넷리스트를 읽는 파서는 KiCad CLI가 필요하지 않으며, KiCad 원본을 PNG로 변환하는 기능만 로컬 범위에서 제외한다.
- 2026-11-15 통합 검증 환경은 OSC Compose 프로젝트의 127.0.0.1:8011이다. 공식 PDF 회로도 수신과 LLM 정격 분석을 확인했다. 전용 8010 Compose의 검증 범위는 설정 검사다.

## AC
- GIVEN 운영 DB 주소가 기존 .env에 있음 WHEN local Compose를 해석함 THEN 모든 DB 사용 서비스는 내부 db만 가리키고 renderer 서비스는 존재하지 않는다.
- GIVEN 로컬 서비스를 시작함 WHEN /login과 /health를 조회함 THEN 200이고 /api/auth/demo는 404다.
- GIVEN 새 로컬 계정 WHEN 정상 로그인·프로젝트 생성·대화 저장·재조회함 THEN 실제 API/로컬 DB에 저장되며 기존 운영 프로젝트는 없다.
- GIVEN 기존 데모 서버 실행 중 WHEN 로컬 서비스를 시작함 THEN 기존 서버를 중단하거나 포트를 재사용하지 않는다.
- GIVEN 벡터 캐시가 부족함 WHEN 적재를 준비함 THEN 부족한 수를 알리고 유료 임베딩 호출 없이 중단한다.
- GIVEN 유료 검증을 실행하지 않음 WHEN 결과를 보고함 THEN 로그인/저장 검증과 모델·검색 성공 미검증을 구분한다.
- GIVEN 실제 API 연결 WHEN .net·.txt 넷리스트를 전송함 THEN 새 회로 버전·대화로 이어지고 과거 대화는 당시 버전을 유지한다. GIVEN 검색 대상이 공개 PDF·PNG·SVG임 WHEN 참고 회로도를 찾음 THEN KiCad 없이 manifest와 PNG 시트를 반환한다. GIVEN 검색 결과가 KiCad 원본만임 WHEN 로컬에서 변환을 요청함 THEN 변환 불가 오류를 공개하고 정적 회로도만 계속 사용할 수 있다. 빈 생성·첨부 계약은 [netlist-conversation-versions.md](netlist-conversation-versions.md)가 후속 계약이며 예전 개발 전용/전송 차단을 대체한다.

## 구현·검증 순서
1. 로컬 Compose를 만들고 해석 결과에서 DB 대상·바인딩·핵심 플래그·비밀 파일 경계를 검사한다.
2. 독립 DB와 정식 이미지를 준비하고 유료 호출 없이 코퍼스/캐시 적재 및 계정을 준비한다.
3. 실제 HTTP 로그인·프로젝트/대화 저장·새로고침 경로와 실행 설정을 검사한다. 비밀값은 결과에 남기지 않는다.
4. 저장소 구조·변경 공백 검사와 실제 실행 결과·미검증 사항을 작업 기록에 남긴다. 커밋·푸시는 하지 않는다.
