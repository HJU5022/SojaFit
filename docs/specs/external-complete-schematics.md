# 공개 프로젝트 완성 회로도

- 상태: 현행
- 기준일: 2026-11-15
- 기준 커밋: STH 07cff382의 로컬 수정과 PR134 통합(미커밋)
- 정본 여부: 정본(공개 프로젝트 완성 회로도 API). 경로·오류 코드의 제품 수준 목록은 [SPEC.md](../../SPEC.md)
- 관련 문서: [backend/projects/PROJECTS.md](../../backend/projects/PROJECTS.md)

## Why

회로 설계자가 부품명이나 용도를 입력해 실제 공개 보드에서 부품과 배선을 함께 확인한다. 측정 항목은 반환된 전체 시트 수와 동일 검색의 추가 외부 호출 수다.

## Goal

- 이름으로 발견한 공개 회로도 파일의 시트, 게시 페이지, 원본 URL, 출처와 확인 가능한 라이선스를 반환한다. 공개 저장소가 출처이면 커밋도 반환한다.
- 15분 동안 같은 검색의 외부 호출을 재사용한다.
- 적용 범위는 백엔드 API와 작업대 원본 회로도 창이다.
- 범위 밖: 데이터시트의 부분 응용 회로, 블록도, 제품 사진, PCB 렌더링 반환. 검증된 완성 회로도가 없을 때 회로 생성·대체 이미지. LLM·Mouser·DigiKey·Nexar 호출과 검색 결과의 DB 저장.

### 다중 후보 대화 (2026-11-16, 백엔드)

같은 이름의 회로도가 여러 제조사·판본·출처에서 검색되면 차이를 설명하고 선택을 묻는다. 여러 회로를 요청한 경우에는 검색된 후보를 모두 소개한다.

POST `/api/external-circuits/schematics/dialogue`는 원래 `question`과 검색어 `queries` 1~3개를 받는다. 검증된 후보 N개의 번호·제조사·모델·판본·파일·출처를 반환한다. 복수 검색어 또는 전체 소개·비교 요청은 `all`, 그 외 여러 후보는 `select`, 한 후보는 `single`로 처리한다. 검색 실패는 검색어별로 구분한다.

백엔드가 모드와 확인할 차이 항목을 정하고 Haiku 5.5가 설명과 질문을 작성한다. 후보 ID 전체와 각 설명의 사실값을 검사하며, 추가·누락·중복 또는 근거 불일치가 있으면 생성문을 채택하지 않는다. 생성 실패는 `unavailable`로 표시하고 후보 상세는 유지한다. 기존 GET의 원본 선택·PNG·프로젝트 소유권 검사와 일일 분석 예산을 재사용한다. 출처의 글은 지시로 실행하지 않으며 업로드한 연결 정보는 LLM에 보내지 않는다.

수용 기준은 동명 후보의 차이 설명·선택 질문, 복수 요청의 전체 소개, 단일 후보와 부분 검색 실패 처리, 잘못된 후보·사실값 거절, 기존 GET·PNG·소유권 계약 유지다. 프런트·DB 저장·배포·기존 데이터시트 인용·일반 대체 판정은 변경하지 않는다.

기존 검색·원본 제공 경로에는 LLM 호출을 추가하지 않는다. 위 POST 대화 경로에 한해 LLM 소개를 허용한다. 검색어 추출·프런트 표시 연결은 호출 측이 맡으며, 대화 API는 받은 검색어를 임의로 바꾸거나 생략하지 않는다.

## What

로그인한 사용자가 회로도 이름을 입력하면 서버가 공개 웹에서 PDF·PNG·SVG와 게시 페이지를 찾는다. 제조사와 비공식 출처를 검색 단계에서 배제하지 않는다. 파일을 안전하게 내려받아 실제 회로도인지 확인한 뒤 PNG로 제공한다. 여러 후보가 있으면 사용자가 원본 URL로 특정해 다시 선택한다. 확인되지 않은 출처는 `public_web`, `evidence_grade=null`로 표시한다.

| 상황 | 응답 | 근거 |
|---|---|---|
| 성공 | 200, 프로젝트와 `images` 배열 | `backend/api/external_circuits.py:59-73` |
| 적합한 회로도 없음, 시트 번호 음수, 만료·변조된 토큰, 시트 번호 범위 밖 | 404 `SCHEMATIC_NOT_FOUND` | `backend/api/external_circuits.py`, `backend/projects/external_schematic.py` |
| 검색어 2자 미만·200자 초과 | 422 | `backend/api/external_circuits.py:62` |
| 공급자 장애 | 502 | `backend/api/external_circuits.py:56` |
| 기능 비활성·설정 누락(서명 키 포함) | 503 | `backend/projects/external_schematic.py:36-39,212-216` |
| GitHub 호출 한도 | 503, `Retry-After` 1~3600초 | `backend/projects/schematic_source.py:48`, `backend/api/external_circuits.py:51` |

기능 활성 조건: `DEMO_MODE=0`, `EXA_WEB_SEARCH_ENABLED=1`, `EXA_API_KEY` 값 있음, `AUTH_SECRET` 32바이트 이상(`backend/projects/external_schematic.py:212-216,36-39`).

## How

### 키워드 검색 후 명시적 후보 선택 (2026-11-15)

- 사용자 결정: 업로드 원본·제품/보드 참고·다이오드 참고 세 분류에 적용한다. 검색어는 발견용 키워드이며 정확한 모델을 추정하거나 업로드 동일성 검사를 대신하지 않는다.
- 3자 이상 단어·품번의 앞부분을 후보 검색과 EDA 배치 부품 대조에서 허용한다. 예: `ATtiny85 dev board AMS111`은 실제 AMS1117 부품을 가진 원본을 찾을 수 있다. 임의 오타 교정·편집거리·등록 모델 목록은 추가하지 않는다. 2자 단어·전압/단위는 기존 경계를 유지한다. 다이오드 용도 키워드처럼 숫자 품번이 없으면 기존 GitHub 경로에서 제한 내에 탐색한다.
- 출처·문서 종류·파일 식별·제조사/명시한 변형·라이선스·시트/이미지·실제 다이오드 사용 검사와 공급자 한도는 유지한다. 업로드 원본의 후보는 실제 EDA의 전체 연결 대조까지 통과해야 한다. 제목/README만으로 숫자 부품이 존재한다고 승인하지 않는다.
- 기존 manifest/choices 계약을 재사용한다. 검색 후에는 검증한 후보 목록을 표시하고 사용자가 선택해야 PNG와 일치 표시를 보여준다. 1개도 선택을 요구한다. 후보 제목에는 원본 파일 식별정보를 표시한다. 기본 후보 선택은 이미 받은 결과로 처리하고 다른 후보는 기존 source_url 선택/캐시 경로를 사용한다.
- AC: Given AMS1117 배치 회로, When `AMS111` 포함 검색, Then 후보로 유지한다. Given 실제 배치 부품이 없는 README 주장/다른 배선, Then 원본 후보로 승인하지 않는다. Given 다이오드 부분 품번/용도, Then 실제 다이오드만 후보로 유지하며 동명 무전기/LED는 거절한다. Given 세 모드의 조회 성공, Then 선택 전 이미지0·일치 표시0, 명시 선택 후 정상 시트/출처 표시, 다른 후보 선택·검색어/모드 변경에도 이전 그림을 잘못 보여주지 않는다. 편집/포커스/재열기 자동 검색은 추가하지 않는다.
- 구현 순서: (1) 검색/EDA 부분 키워드 실패 회귀와 품번 없는 다이오드 탐색 회귀 → 최소 수정, (2) 명시 선택 화면/기존 회귀 → 테스트/빌드, (3) 저장된 실제 원본과 화면으로 연결 일치·다른 배선 차단 확인. 기존 파일만 수정하고 SPEC4 반영은 조장 검토 제안으로 남긴다.

### 검색 대상·입력 안내 (2026-11-15)

- native select와 펼친 option 목록은 기존 다크 메뉴/본문 토큰을 사용해 일반 항목의 밝은 배경·밝은 글자 조합을 방지한다. AC: 검색 대상을 펼쳤을 때 세 항목이 모두 읽히며 마우스/방향키 선택과 기존 포커스를 유지한다. OS가 제어하는 선택 강조와 강제 색상 모드는 유지한다.
- 검색 대상 선택칸 아래의 기본 접힘 `검색 대상 안내`를 펼치면 목적과 동일성 검사 여부를 표시한다. 업로드 원본은 전체 부품·핀 연결 대조, 제품·보드/다이오드 참고는 업로드 회로와 동일함을 뜻하지 않는다고 안내한다.
- 입력칸 아래의 기본 접힘 `검색어 입력 안내·예시`를 펼치면 선택한 대상의 기준·예시·길이·오타/URL 안내를 표시하며 placeholder는 접힘과 관계없이 맞춘다. 두 안내는 독립적인 native details/summary를 사용한다. 공개 보드·프로젝트명/포함 부품, 제조사·제품군·모델, 다이오드 품번/용도를 구분하고 후보에서 실제 모델·파일을 확인하도록 안내한다. D1/U1은 품번 대신 쓰지 않도록 안내한다.
- 3자 이상 앞부분 검색과 오타 자동 보정의 차이를 안내한다. 기존 2~200자/다이오드 2~194자와 URL 대신 이름·품번 입력 기준을 유지한다.
- AC: Given 검색 창 최초 진입, Then 두 안내는 접혀 있고 선택칸·입력칸·검색 버튼은 보인다. When 안내 하나를 펼치거나 접음, Then 해당 안내만 바뀌고 입력/선택/조회 상태는 유지되며 검색 요청0이다. When 원본→제품·보드 참고→다이오드 참고를 선택, Then 펼친 안내의 설명·기준·예시·placeholder·글자 수 상한이 함께 바뀌고 입력값은 보존된다. 선택칸과 입력칸은 aria-describedby로 해당 안내를 연결한다. 프로젝트 없는 제품·보드 검색에도 동일 접힘 안내를 제공한다.
- API 형식·출처/동일성 검증은 유지한다. 키워드/명시 선택 동작은 위 계약을 따르며 주요 SPEC 4절 반영은 조장 검토 제안으로 남긴다.

### 공급자 한도 초과 후 재조회 차단 (2026-11-15)

- 공급자 호스트별 제한 해제 시각을 프로세스 메모리에 최대 128건 보관한다. GitHub API는 인증 토큰의 비가역 fingerprint로 구분하며 토큰값은 기록하지 않는다. 성공 캐시는 그대로 재사용한다.
- 제한 중인 호스트에는 후보·검색어가 달라도 새 HTTP 요청을 보내지 않는다. 동일 GitHub 공급자의 후보 검사는 한도 초과를 확인하면 중단하고 다른 웹 공급자와 이미 검증한 정상 결과는 유지한다.
- 같은 검색의 한도 오류도 원래 제한 해제 시각까지 보관한다. 재클릭은 검색·검증을 재실행하지 않고 감소한 Retry-After만 반환한다. 15분 성공 캐시 TTL이 지나도 제한 중에는 재조회하지 않으며, 해제 후 사용자가 요청하면 기존 상한 안에서 다시 검사한다.
- AC: Given 첫 GitHub 후보가 429/한도 403, When 후보 반복 및 제한 중 동일 검색 재요청, Then 첫 검사 1회·추가 HTTP 0회·대기 시각 연장 0회. Given 다른 검색/다른 URL, Then 제한 호스트 요청 0회이고 다른 호스트는 유지. Given 토큰 변경 또는 제한 해제, Then 해당 범위는 재조회 가능. Given 정상 후보와 제한 후보가 함께 있음, Then 정상 후보와 기존 선택을 보존한다.
- 범위 밖: 유료 실조회·8010 반영·운영 변경·분산 캐시. 주요 SPEC 4절에는 위 재요청 차단 계약을 PR 코멘트로 반영 제안한다.

- 프로젝트 원본 모드는 `project_id/circuit_version/thread_id` 소유 snapshot을 사용한다. 별도 제품·다이오드 참고 검색은 `reference_only=true`이며 프로젝트 문맥과 함께 지정하면 422다. `component_type=diode`는 참고 조회와 194자 이하 검색어에만 허용한다. 화면은 프로젝트 원본을 기본값으로 유지하고 참고 모드에서는 업로드 회로와 동일한 회로라는 뜻이 아님을 알린다. 쿼리 캐시도 문맥과 모드별로 분리한다.
- KiCad 원격 렌더러에는 고정 공개 source와 `include_netlist=true`만 보낸다. 업로드 원본·부품·연결은 보내지 않는다. 렌더러는 같은 선택 계층의 실제 CLI export를 정규화해 PNG 시트와 함께 `connections`로 반환한다. API가 응답 크기·PNG·시트 수와 전체 부품/핀 연결 대응을 검증한다. 연결 누락·불일치·잘못된 형식은 원본 승인에 쓰지 않고, 참조 끝 숫자만 바뀐 같은 회로와 복잡한 대칭 구조는 기존 제한된 완전 대응 검사로 유지한다. 이전 renderer 응답은 참고 조회에만 쓸 수 있다.

### 업로드 회로와 외부 회로도의 동일성

- 업로드 프로젝트의 조회는 project_id/circuit_version와 선택적 thread_id를 manifest·시트 GET에 함께 전달한다. 서버는 인증 사용자 소유의 현재/대화 고정 회로를 먼저 읽고 버전을 확인한다. 넷리스트·부품·핀 연결은 외부 검색 서비스에 전송하지 않는다. 일반 참고 검색은 reference_only=true를 명시해야 하며 프로젝트 문맥과 함께 지정할 수 없다. 문맥도 참고 검색 표시도 없는 이전 요청은 422로 거절한다.
- 외부 KiCad 원본에서 제한된 CLI로 넷리스트를 직접 내보내 업로드 회로와 부품 값/풋프린트·참조 접두어 및 모든 핀 번호의 net 분할을 대조한다. net 이름/번호·순서와 참조의 끝 숫자 차이는 무시할 수 있지만, 부품 사이 일대일 대응과 전체 핀 연결의 일치를 실제로 확인해야 한다. 부품 목록·국소 연결/구조 해시만으로 승인하지 않는다. 같은 부품 목록이라도 연결·값·풋프린트·접두어·누락/추가 부품이 다르면 거절한다. 중복 핀/모호한 연결은 거절하며 PCB/실물 동작까지 같다고 추정하지 않는다. 재번호 탐색은 부품256개/넷1024개/핀8192개·후보대응10000회·2초 상한이며 초과하면 승인하지 않는다. 참조까지 같은 기존 전체 연결 일치는 기존 제한으로 빠르게 확인한다.
- 프로젝트 조회는 전체 연결 대조를 통과한 native EDA를 직접 변환한 이미지만 제공한다. 공식 PDF/PNG·일반 공개 PDF처럼 연결 정보 대조가 불가능한 자료는 프로젝트 원본으로 승인하지 않는다. 이름 기반 일반 참고 검색의 기존 출처 검증과 구분한다.
- 대칭 부품 탐색에서는 이미 일대일 대응이 확정된 net·핀 번호에 연결된 후보만 교집합으로 좁힌 뒤 전체 대응을 검사한다. 상한을 늘리거나 부분 연결만으로 승인하지 않으며 재번호된 긴 고리·반복 회로도 기존 상한 안에서 보존한다.
- 검색/이미지 캐시와 서명은 회로 fingerprint를 포함한다. 연결이 다른 회로의 결과나 일반 참고 검색의 토큰을 프로젝트 시트 조회에 재사용하지 못한다. 이미지 GET에서도 소유권·대화/회로 버전·fingerprint를 확인하고 캐시가 비면 다시 대조한다. 버전이 달라도 정규화된 부품·전체 핀 연결이 같으면 검증 캐시를 공유할 수 있다.
- 화면은 프로젝트/대화/버전별로 검색 상태를 분리하고 동일성 미확인 결과는 표시하지 않는다. 일치 결과에는 업로드 회로 버전과 부품·핀 연결 일치를 명시하고 실패 시 동일성 확인 실패를 안내한다. 주요 SPEC 반영은 조장 검토 제안이다.

추가 AC: 같은 이름·같은 BOM의 다른 배선 거절, net 이름/순서·참조 끝 숫자만 바뀐 동일 회로 허용, 대칭 부품의 완전 대응 및 국소 구성이 같아도 전체 연결이 다른 회로 거절, 탐색 상한 초과 시 거절, 부품 값/핀/풋프린트/접두어/구성 변경 거절, PDF 단독 거절, 다른 소유자/프로젝트/대화/버전 조회 거절, 다른 회로 캐시·토큰 재사용 거절, 새 버전 전환 시 이전 도면 제거와 과거 대화의 회로 고정, 일반 참고 검색 동작 보존.

### 404 원인 구분과 공식 PDF 식별 보완

- 구현 순서: 아래 AC의 실패 회귀를 추가한 뒤 서비스 실패 결과·API·화면을 연결하고, 공식 페이지 링크 검증과 전압 표기를 보완한다. 마지막으로 실제 네트워크를 차단한 모의 회귀와 프런트 검사·빌드를 실행한다. 유료 검색·모델·DB·배포는 실행하지 않는다.
- 공통 오류 계약의 HTTP404와 `SCHEMATIC_NOT_FOUND`는 유지한다. `X-Schematic-Failure`는 `no_candidates`(정제 후 후보 없음), `validation_failed`(후보가 있으나 검증 실패), `not_found`(선택 URL·토큰 등 기존 실패)를 구분하며 한국어 응답 문구도 달리한다. 화면은 해당 문구를 보존한다. 실패 원인은 기존 15분 캐시에서도 유지한다.
- 서버는 요청 ID 문맥에 검색 원시 결과 수·정제 후보 수·검사/변환 탈락 수를 제한된 단계명과 함께 기록한다. 검색어·제목·URL·본문·키는 기록하지 않는다. 원시 결과 없음과 정제 탈락은 이 기록으로 구분한다.
- `/datasheets/` 같은 상위 폴더명만으로 회로도를 거절하지 않는다. 실제 파일명의 데이터시트·다른 모델 검증과 PDF 시트·형식·해시·SSRF 제약은 유지한다.
- 전압 문자열은 모델·리비전과 구분하며 `5V`/`5 V`, `3.3V`/`3.3 V`를 같은 표기로 확인하되 `3.3V`와 `33V`를 섞지 않는다. PDF 본문에서 확인할 수 없으면, 허용된 제조사 공식 페이지를 제한된 GET으로 읽어 요청 제품명·전압과 해당 원본 파일의 직접 연결이 함께 확인될 때만 보완한다. 검색 결과 제목만으로 통과시키지 않는다. 모델/리비전은 이 보완으로 우회하지 않는다.

추가 AC:
- Given 후보0과 후보1의 검증 탈락, When 같은 요청을 반복, Then 서로 다른 원인/안내를 유지하고 캐시 시간 내 검색을 반복하지 않는다.
- Given 검색 결과1이 정제에서 제외, When 검색 완료, Then 원시1/정제0 기록을 남기고 키·질문·원문을 로그에 남기지 않는다.
- Given 추출 본문이 없는 정상 PDF와 공식 페이지의 제품명·전압·직접 링크, When 검사, Then `/datasheets/` 폴더에서도 통과한다.
- Given 제3자 페이지, 다른 파일 링크, 검색 제목에만 존재하는 전압, 또는 3.3V 대신33V 근거, When 검사, Then 통과시키지 않는다.
- Given 다른 모델·리비전 또는 데이터시트 파일명, When 공식 링크가 있어도 검사, Then 기존 거절을 유지한다.

### 회로도 확대·축소와 이동

- 이미지 표시 영역은 모달/시트의 레이아웃으로 고정한다. 50~400% 배율은 영역 크기 대신 이미지 transform에만 적용하고 100%는 영역에 맞춘 크기다. 출처/라이선스와 검색 입력은 이미지 변형에 포함하지 않는다.
- 기본 포인터(마우스 왼쪽/터치) 드래그와 방향키로 이미지 위치를 이동한다. 포인터 캡처로 영역 밖에서 놓아도 이동을 종료하고 취소/캡처 해제도 처리한다. 이미지 전체가 영역 밖으로 사라지지 않도록 위치를 제한한다.
- 이미지 위 휠 위/아래로 해당 시트만 25%씩 확대/축소한다(50~400%). 로딩/실패 상태에서는 휠을 가로채지 않고, 표시된 이미지의 휠은 문서 스크롤·브라우저 확대와 겹치지 않게 처리한다. 상단의 배율 숫자·확대/축소 버튼은 제거한다.
- 이미지 영역 우측 상단의 고정 맞춤 아이콘은 100%와 중앙 위치를 함께 복원하며 이미100%인 상태에서도 동작한다. 방향키 이동, +/− 확대/축소, Home 맞춤을 키보드로 제공하며 아이콘에는 접근 가능한 이름을 둔다. 다중 시트의 배율·이동·맞춤은 각각 독립적이다. 확대·축소/드래그/맞춤은 외부 검색을 호출하지 않는다.
- AC: Given 같은 시트의100/75/50/200% 배율, When 변경, Then 표시 영역의 너비/높이는 유지되고 이미지만 변형된다. Given 드래그/방향키로 이동한 이미지, When 맞춤, Then 중앙/100%로 복원한다. Given 포인터 취소·오른쪽 클릭·다른 포인터, When 이동, Then 활성 이동이 남거나 시작되지 않는다. 로컬 이미지/모의 응답으로 검증한다.

### OSC와 main 통합 시 유지하는 계약

- 작업대의 화면 구성과 이미지 확대·이동은 main을 기준으로 유지한다. 질문 접수 실패 시 초안·첨부를 보존하고 서버 실행 접수 후에도 새로 입력한 초안을 지우지 않는다. 첨부는 서버의 단일 파일 계약에 맞추며 다이오드 외 부품은 새 판정을 시작하지 않고 저장된 기록은 읽을 수 있게 한다.
- 다이오드 검색은 `component_type=diode`로 제품·보드 검색과 구분한다. 실제 배치 품번과 다이오드 구조를 검증하며, SS33 무전기처럼 품번만 같은 자료는 제외한다. 일반 `Device:D`와 사용자 정의 다이오드는 실제 연결·핀 근거가 있으면 검사한다.
- 외부 다이오드 검색은 공식·공개 웹 후보를 먼저 검증하고, 정상 결과가 없으면 BOM·독립 GitHub 검색 경로에서 최대 24개 저장소를 검사한다. 여러 완전한 원본과 자체 계층이 완전한 하위 회로를 고정 commit·root별로 구분해 선택할 수 있게 한다. discovery는 최대 128파일·파일당 4MiB·총 25MiB로 제한한다. 렌더링은 검증한 선택 계층만 직접 다운로드하며 파일당 10MiB·총 25MiB·최대 20시트로 제한한다. 라이선스·누락·순환·출처·SSRF 검증은 유지한다.
- main의 비회로도 이미지·자료 유형·공식 링크·제품 변형·전압 검증과 404 원인 구분을 유지한다. 후보 선택은 검증된 원본에 한정하며 실패한 원본을 다른 회로로 바꾸지 않는다. 일부 원본 검사·렌더링이 한도·외부 오류로 실패하면 오류와 재시도 정보를 보존하고, 정상 후보를 유지하되 Retry-After 또는 60초 후 같은 검색의 후보·선택 캐시를 재검사한다.
- 출처·원본 링크는 이미지 위에 표시한다. 제조사 공식 여부와 커뮤니티 라이선스 선언은 별개의 문구로 안내한다. KiCad 10 전용 renderer는 API 이미지와 분리한다.
- AC: Given main의 제품·이미지 검증 및 확대·이동 회귀와 OSC의 다이오드 검색·후보 선택·초안·첨부 회귀, When 통합본을 검사, Then 양쪽 테스트가 함께 통과하고 8011의 실제 API·화면 결과와 외부 한도로 미검증된 항목을 구분해 기록한다.

### Renderer 구성과 배포 안내

- API 최종 이미지는 KiCad를 포함하지 않는다. `Dockerfile`의 `renderer` target이 KiCad 10과 `/health`, `/render`를 제공하며, API는 `KICAD_RENDERER_URL`이 있을 때 KiCad 원본만 이 서비스로 보낸다. API 이미지와 renderer 이미지는 서로 다른 Cloud Run 서비스로 배포한다.
- 선택 KiCad 파일 다운로드의 한도 오류는 자료 손상으로 분류하지 않는다. renderer는 한도 오류를 `503`과 제한된 `Retry-After`로 전달하며, API도 기존의 `503`/`Retry-After` 계약을 유지한다. 일반 변환 장애와 잘못된 원본의 `422`는 별도로 처리한다.
- 로컬 실제 API Compose는 `KICAD_RENDERER_URL`을 비우고 KiCad renderer를 시작하지 않는다. 로컬 검색·표시 대상은 공개 PDF·PNG·SVG 회로도와 정적 회로도다. KiCad 원본만 있는 결과는 PNG로 변환하지 않는다. 실제 LLM·외부 검색은 `DEMO_MODE=0`, `DEMO_REPLAY=0`과 공급자 키 설정으로 활성화한다.
- Cloud Run의 API 환경변수 `KICAD_RENDERER_URL`에는 renderer의 HTTPS 서비스 URL만 넣는다. Cloud Run에서 실행될 때 API는 metadata server에서 그 URL을 audience로 한 ID token을 받아 `Authorization: Bearer`로 호출한다. renderer는 비공개로 두고 API 서비스 계정에 renderer의 `roles/run.invoker`를 부여해야 한다. 이 문서의 명령은 예시이며 실제 Cloud Run 배포·호출은 수행하지 않았다.

예시 명령(자리표시자만 사용): Artifact Registry 저장소·Cloud Run의 프로젝트/리전·서비스 계정은 미리 준비한다. 두 컨테이너는 8000 포트로 실행하므로 배포에도 `--port 8000`을 지정한다. API의 DB·인증·Exa 환경변수와 Secret 설정은 기존 배포 설정을 유지하며, 아래 명령은 renderer 연결에 필요한 부분만 보여준다. `RENDERER_SERVICE_URL`은 renderer 배포 후 출력되는 실제 HTTPS 서비스 URL로 바꾼다.

```bash
docker build --target renderer -t REGION-docker.pkg.dev/PROJECT/REPOSITORY/sojafit-renderer:TAG .
docker build -t REGION-docker.pkg.dev/PROJECT/REPOSITORY/sojafit-api:TAG .
docker push REGION-docker.pkg.dev/PROJECT/REPOSITORY/sojafit-renderer:TAG
docker push REGION-docker.pkg.dev/PROJECT/REPOSITORY/sojafit-api:TAG
gcloud run deploy sojafit-renderer --image REGION-docker.pkg.dev/PROJECT/REPOSITORY/sojafit-renderer:TAG --port 8000 --no-allow-unauthenticated --service-account RENDERER_SERVICE_ACCOUNT
gcloud run deploy sojafit-api --image REGION-docker.pkg.dev/PROJECT/REPOSITORY/sojafit-api:TAG --port 8000 --update-env-vars KICAD_RENDERER_URL=RENDERER_SERVICE_URL --service-account API_SERVICE_ACCOUNT
gcloud run services add-iam-policy-binding sojafit-renderer --member serviceAccount:API_SERVICE_ACCOUNT --role roles/run.invoker
```

배포 플래그와 서비스 간 ID token의 audience·metadata server 방식은 [Cloud Run container deployment](https://cloud.google.com/run/docs/deploying), [Cloud Run service-to-service authentication](https://cloud.google.com/run/docs/authenticating/service-to-service), [gcloud run deploy reference](https://cloud.google.com/sdk/gcloud/reference/run)를 따른다. Compose profile 사용법은 [Docker Compose profiles](https://docs.docker.com/compose/how-tos/profiles/)를 따른다.

### API

| 경로 | 동작 | 근거 |
|---|---|---|
| `GET /api/external-circuits/schematics?q=&source_url=&component_type=diode` | 이름으로 찾은 회로도와 순서가 있는 `images`(`sheet`, `url`), 다른 검색 후보 `choices`를 반환한다. `source_url`은 선택 사항이며 같은 검색의 검증된 후보 URL일 때만 허용한다. `component_type=diode`도 선택 사항이며 지정하면 검색어는 trim 후 2~194자다. 일반 검색어는 2~200자다 | `backend/api/external_circuits.py` |
| `POST /api/external-circuits/schematics/dialogue` | 원래 질문과 검색어 1~3개로 검증된 모든 후보 상세를 반환한다. 단일 대상의 여러 후보는 차이 설명과 선택 질문, 복수·비교 요청은 전체 소개. 후보·생성 상태·검색별 실패를 분리하며 인증·Origin·기존 일일 예산을 적용한다 | `backend/api/external_circuits.py`, `backend/projects/schematic_dialogue.py` |
| `GET /api/external-circuits/schematics/{signed_token}/{sheet_index}` | 같은 로그인 세션에서 PNG 반환. 임의 외부 URL은 받지 않는다 | `backend/api/external_circuits.py:75-86` |

세 경로 모두 로그인이 필요하다. 응답 헤더는 `Cache-Control: private, no-store`다. PNG는 `X-Content-Type-Options: nosniff`, `Content-Disposition: inline`을 더한다. POST의 상세 요청·응답·실패 계약은 [API.md](../../backend/api/API.md)의 회로도 후보 대화 절을 따른다. LLM 소개는 한 번에 24후보까지이며 이를 초과하면 생성 상태만 `unavailable`로 두고 후보 상세는 전부 유지한다.

### 검색과 검증

| 단계 | 내용 | 근거 |
|---|---|---|
| 1. 후보 검색 | 회로도 이름으로 Exa 공개 웹을 1회 검색하고, 제조사를 식별할 수 있으면 해당 공식 도메인으로 보강 검색한다. 사전 지정 모델 URL 없이 PDF·PNG·SVG 및 게시 페이지의 링크 글자·제목·이미지 설명에서 회로도 파일을 찾는다. 응답은 512 KiB 상한 | `backend/projects/external_circuit_search.py` |
| 2. 이름·이미지 확인 | 회로도 표식이 없는 사진·PCB·배선·데이터시트와 모델·변형이 다른 후보, 축약 도면을 제외한다. 검색어와 제목·게시 페이지·원본 URL 및 PDF 본문을 대조한다. 이름 일치를 우선하고, 제조사 공식 회로도 이미지가 안내서 PDF보다 앞선다 | `backend/projects/external_circuit_search.py`, `backend/projects/schematic_render.py` |
| 3. 출처 표시 | 확인된 제조사 공식 도메인의 게시 페이지와 해당 제조사 원본의 연결을 확인하면 `manufacturer_official`, 2등급으로 표시한다. 그 밖의 공개 웹 자료는 `public_web`, 등급 미지정으로 표시한다. 공개 GitHub 저장소 검증 경로는 후보가 없거나 무효일 때 계속 사용할 수 있다 | `backend/projects/external_circuit_search.py`, `backend/projects/external_schematic.py` |
| 4. 파일 검증·변환 | 각 후보의 HTTPS·공개 IP·형식·크기를 제한하고 연결 IP를 DNS 검증 결과에 고정한다. 모델 식별과 원본 SHA-256을 확인해 PNG로 변환한다. 다중 페이지 PDF는 목차를 제외한 회로도 표시 페이지만 반환한다. 일시적인 원본 요청 오류는 검색 전체에서 최대 1회 재시도하며, 한 후보가 호출 제한에 걸리면 다음 후보를 검사한다 | `backend/projects/schematic_discovery.py`, `backend/projects/schematic_render.py`, `backend/projects/external_schematic.py` |
| 5. 결과 선택 | 첫 유효 후보와 함께 최대 5개의 이름·출처 후보를 전달한다. 사용자가 다른 후보를 선택하면 서버가 같은 검색 결과에 포함된 URL인지 검사한 후 파일을 다시 검증한다 | `backend/projects/external_schematic.py`, `frontend/src/Schematic.tsx` |

- 공개 GitHub 저장소 후보의 PNG·PDF 이미지는 고정 커밋의 `raw.githubusercontent.com` 원본에서 받는다. 제조사 페이지가 연결한 공식 GitHub 파일은 해당 원본 URL에서 받으며, 재조회 시 SHA-256이 달라지면 버린다. 그 밖의 공개 웹 후보는 검색으로 확인한 원본 URL에서 받는다.
- 제조사 도메인 보강 검색은 검색어에서 식별한 Adafruit·SparkFun·Seeed·Arduino·Pololu·Olimex·Raspberry Pi·PJRC의 공식 도메인으로 제한한다. 제조사 페이지의 GitHub 자료는 허용한 공식 조직의 직접 링크만 원본으로 취급한다.
- PDF는 전체 회로도 파일의 시트를 목표 300 DPI로 변환한다. 여러 페이지의 일반 안내서는 회로도 표시 페이지를 식별할 때만 그 페이지를 반환한다. 시트당 출력은 4,000만 픽셀 이내다.
- KiCad 원본은 renderer가 배포된 환경에서만 검증한 선택 계층의 파일을 고정 commit에서 직접 다운로드해 `kicad-cli`로 PDF로 내보낸 뒤 PNG로 렌더링한다. `asset_paths`가 없는 기존 source만 제한된 저장소 압축본 경로를 사용한다. 운영 renderer 이미지가 KiCad 10을 설치하고 기본 API 이미지와 로컬 실제 API 이미지는 설치하지 않는다(`backend/projects/schematic_render.py`, `Dockerfile`).
- SVG는 허용 요소 목록에 없는 요소, 외부 참조, 스크립트, 이벤트 속성을 거절한다(`backend/projects/schematic_render.py:43`).
- 다중 시트 프로젝트는 모든 시트를 순서대로 반환한다. 원본과 시트 수가 다르면 그 후보를 버린다(`backend/projects/external_schematic.py:154-155`).
- 구형 `.sch`는 프로젝트가 제공한 전체 PNG·SVG·PDF가 있을 때 지원한다. KiCad 9.0.2로 구형 원본을 직접 내보낼 때 배치된 심볼이 빠진 사례가 있다(설계 시점 관찰, 재측정하지 않음).

### 서명 토큰과 캐시

| 항목 | 값 | 근거 |
|---|---|---|
| 서명 | `AUTH_SECRET`에서 파생한 키로 HMAC-SHA256. 저장소, 커밋, 라이선스, 저작자, 원본 경로, 자산 종류, 자산 경로, 시트 수, 만료 시각을 서명한다. 토큰 길이 4,096자 이내 | `backend/projects/external_schematic.py:36-83` |
| 유효 시간 | 900초 | `backend/projects/external_schematic.py:20` |
| 검색 결과 캐시 | 항목 128개, 정규화한 검색어(공백 정리, 소문자) 키. 성공과 결과 없음 모두 보관 | `backend/projects/external_schematic.py:133-137,161-170` |
| 시트 PNG 캐시 | 항목 64개, 총 128 MiB, 키는 검증된 원본 식별자 | `backend/projects/external_schematic.py:133-138` |
| 동시 요청 | 같은 키의 동시 요청은 진행 중인 하나를 공유한다 | `backend/projects/external_schematic.py:86-129` |
| 인스턴스 교체 | 캐시가 비어도 유효한 토큰에서 고정 원본을 다시 받아 만든다 | `backend/projects/external_schematic.py:173-185` |

캐시는 서버 프로세스 메모리에만 있다. 검색어·이미지·저장소 압축본은 DB, 대화 상태, 로그에 저장하지 않는다. 변환용 임시 파일은 요청 중에만 존재한다.

### 모듈

| 파일 | 역할 |
|---|---|
| `backend/api/external_circuits.py` | 인증, 입력 검증, 공개 오류 매핑, 응답 헤더 |
| `backend/projects/external_circuit_search.py` | Exa 호출, GitHub 저장소 후보 정제 |
| `backend/projects/schematic_discovery.py` | GitHub 메타데이터·트리·원본 해석, 이미지 후보 선택, 안전한 다운로드 |
| `backend/projects/schematic_source.py` | 허용 라이선스 목록, 검증된 원본 식별자, 서비스 오류 |
| `backend/projects/schematic_render.py` | PNG·PDF·SVG 검증과 PNG 변환, KiCad 원본 처리 |
| `backend/projects/external_schematic.py` | 서명 토큰, 캐시, 후보 순회 |
| `backend/projects/schematic.py` | KiCad subprocess 실행 경계 |

### 자원 상한

| 항목 | 상한 | 근거 |
|---|---|---|
| Exa 응답 | 공개 웹 검색 512 KiB, GitHub 검색 256 KiB | `backend/projects/external_circuit_search.py` |
| GitHub 저장소·커밋 응답 | 각 256 KiB | `backend/projects/schematic_discovery.py:352` |
| GitHub 재귀 트리 응답 | 2 MiB, 항목 5,000개 | `backend/projects/schematic_discovery.py:111,368` |
| discovery 원본 EDA 파일 | 파일당 4 MiB, 합계 25 MiB, 최대 128개 | `backend/projects/schematic_discovery.py` |
| 렌더링할 선택 계층 | 파일당 10 MiB, 합계 25 MiB, 최대 20시트 | `backend/projects/schematic_render.py` |
| PNG·SVG 이미지 | 10 MiB | `backend/projects/schematic_render.py:30` |
| PDF | 20 MiB, 20쪽 | `backend/projects/schematic_render.py:31,35` |
| 저장소 압축본 | 압축 25 MiB, 해제 100 MiB, 항목 5,000개 | `backend/projects/schematic_render.py:32-34` |
| 시트 수 | 20 | `backend/projects/schematic_render.py:35` |
| 시트당 출력 | 4,000만 픽셀 | `backend/projects/schematic_render.py:36` |
| 변환 subprocess | 제한 시간 30초 | `backend/projects/schematic.py:8` |
| 외부 요청 | HTTPS, 공개 IP, 표준 포트, 사용자정보 없음. 각 후보에서 검증한 호스트와 공개 IP로 연결한다. 리다이렉트는 hop마다 재검증, 최대 4회 | `backend/projects/schematic_discovery.py` |
| GitHub 인증 | `GITHUB_TOKEN`이 있으면 API 호스트 요청에만 붙인다. 없으면 익명 | `backend/projects/schematic_discovery.py:61-63` |

## 화면

작업대 왼쪽 "회로" 구역의 원본 회로도(`frontend/src/Schematic.tsx`)는 저장된 데모 도면이 없고 넷리스트가 있는 프로젝트를 열 때 프로젝트 이름으로 이 API를 한 번 호출하고, 찾지 못하면 사용자가 다른 이름으로 다시 찾을 수 있다(2026-11-16 변경, 이전에는 버튼을 누를 때만 호출). 여러 출처가 검색되면 후보 목록에서 다른 원본을 선택할 수 있다.

- 검색어 칸의 처음 값은 프로젝트 이름이다. 프로젝트 응답에 넷리스트 제목·보드 이름이 없다. 사용자가 고칠 수 있다.
- 프로젝트를 열 때 한 번 자동으로 보낸다. 같은 탭에서는 (프로젝트, 회로 버전)마다 다시 보내지 않는다(찾은 결과 14분, 실패는 탭이 열려 있는 동안 남기고 사용자가 다시 찾을 때만 다시 보냄, 직접 찾기가 실패해도 앞서 찾은 결과 유지, `frontend/src/schematicSearch.ts`). 검색 중에는 찾는 중 안내가 보인다.
- 검색어가 2자 미만이거나 일반 검색에서 200자 초과(다이오드 검색에서 194자 초과)이면 버튼이 꺼지고 규칙 문구를 보인다. API를 부르지 않는다.
- `images`의 모든 시트를 순서대로 보이고 각 시트에 출처·라이선스·원본 링크(`source_url`)와 게시 페이지를 붙인다. 공식 여부를 확인할 수 없는 출처는 등급 미지정으로 표시한다.
- 이미지 요청이 실패하면(서명 900초 만료 포함) "다시 검색하기"로 새 서명 주소를 받는다.

| 응답 | 화면 |
|---|---|
| 404 `SCHEMATIC_NOT_FOUND` | 공개된 원본 회로도를 찾지 못했다는 안내. 검색어를 바꿔 다시 찾을 수 있고 연결 개념도는 계속 볼 수 있다 |
| 502 | 잠시 후 다시 시도 안내 |
| 503 + `Retry-After` | 그 시간(60초 이상이면 분)을 안내하고 검색 칸은 유지 |
| 503, `Retry-After` 없음 | 이 환경에서는 쓸 수 없다는 안내. 검색 칸을 숨겨 재시도를 권하지 않는다 |

## AC

1. 등록되지 않은 제조사 회로도 이름으로 검색하면 공식 게시 페이지의 회로도 파일을 찾아 PNG와 원본 링크를 제공한다.
2. 비공식 회로도 이름으로 검색하면 공개 출처의 실제 이미지와 게시 페이지를 제공하되 검증되지 않은 공식 등급을 주장하지 않는다.
3. 후보가 데이터시트나 PCB 이미지만 제공하면 다음 후보를 검사하고, 모두 탈락하면 `SCHEMATIC_NOT_FOUND`를 반환한다.
4. 여러 후보가 나오면 사용자가 선택할 수 있고, 검색 결과에 없던 URL을 `source_url`로 제출해도 서버가 내려받지 않는다.
   - Given 사용자가 선택한 공식·EDA 없는 PDF 제한 허용, When 같은 게시자의 안전한 HTML이 해당 PDF를 회로도로 직접 연결하고 게시 제품명·실제 PDF의 한 줄 제품명이 검색어와 일치, Then 단일 벡터 PDF에서 서로 다른 부품 참조6개/종류2개, 비영점 직교 선분8개/서로 다른 분기2개를 확인한 경우에만 public_web/등급 없음으로 허용한다. 이는 회로 구조의 보수적 휴리스틱이며 의미·설계 정확성을 보증하지 않는다. PNG/SVG·스캔/래스터 PDF·다중 문서/부분 회로·PCB/데이터시트/심벌·본문 없는 자료는 이 경로로 허용하지 않는다. 기존 상용 보드 원본 검색의 제조사 대조/EDA 경계를 유지하고 별도 응용 회로로 우회하지 않는다. 최초 fingerprint와 검사/변환 hash 일치·공개 HTTPS/host/본문 크기/worker 시간·메모리/캐시/미확인 라이선스 계약을 유지한다. 주요 SPEC 반영은 조장 검토 제안이다.
   - 게시 근거 없는 공개 PDF 직접 주소만 검색된 일반 프로젝트는 게시 페이지 발견을 딱1회 보완한다. 원본 URL이 겹치면 직접 주소보다 실제 게시 페이지 연결을 가진 결과를 보존한다. HTML 제목의 data-href 다운로드는 화면의 회로도 문구와 함께 읽으며 스크립트는 실행하지 않고 기존 URL/호스트 검사를 유지한다. 상용 보드 원본 검색은 이 발견 보완/공개 PDF 예외로 우회하지 않는다.
   - Given 제조사 원본이 없는 공개 GitHub 프로젝트, When 실제 배치 부품/배선과 허용 라이선스·고정 commit·완전한 EDA 계층이 확인되고 검색어를 대조, Then `dev board`/`development board`, `tiny85`/`ATtiny85`, README의 `Tiny85FanControl`/띄어 쓴 `tiny85 Fan Control` 표기 차이 때문에 정상 원본을 버리지 않는다. 숫자 모델은 여전히 실제 배치 부품에서 확인하며 README의 모델 주장이나 용도가 다른 자료로 대체하지 않는다. 승인 이미지는 EDA 원본을 직접 변환하고 제조사 원본과 대조되지 않은 공개 미리보기 이미지는 승인하지 않는다. 주요 SPEC 반영은 조장 검토 제안이다.
   - Given 공개 파일의 식별정보가 잘못될 수 있음, When 후보 승인, Then 파일명·제목·게시 설명만으로 미확인 공개 원본을 승인하지 않고 같은 검색에서 실제 검사/렌더가 성공한 제조사 원본과 SHA256이 일치한 공개 미러를 남긴다. 별도로 위의 게시 근거·PDF 내부 내용 검사에 통과한 일반 프로젝트 PDF만 제한 허용하며 나머지 불확실한 파일은 보수적으로 제외한다. 상용 보드 요청은 커뮤니티 응용 회로로 우회하지 않으며 일반 프로젝트의 GitHub 출처는 EDA 원본을 직접 변환한다. 이 검사는 설계 오류까지 판별하는 기능은 아니다. SPEC 반영은 조장 검토 제안이다.
   - Given 공식 제조사 설계 ZIP, When 회로도 탐색/검사, Then 제조사 허용 호스트의 압축 자료에서 명확한 회로도 PDF가 하나일 때만 제한된 크기로 읽고 기존 PDF 식별·시트·변환 검사를 수행한다. ZIP 항목 수/해제 크기/경로/암호화/중복 회로도는 검사하며 외부 ZIP은 승인하지 않는다. manifest의 source_url/source_file은 ZIP을 가리키고 asset_kind/pdf SHA256은 내부 회로도 PDF를 식별한다. 새 모델별 URL/해시 상수 없이 공식 페이지 링크에서 발견한다. SPEC 반영은 조장 검토 제안이다.
   - 원본 대조 이전 정책의 서명 주소는 version3 전환으로 무효화한다. 새 미러 서명은 실제 원본 일치를 확인한 후에만 발행하며 모델·리비전은 원본 기준을 따른다. 이전 주소의 이미지 오류는 기존 수동 재검색 흐름을 사용한다.
   - 제조사 원본을 고르는 단계도 검색업체 제목만 믿지 않고 실제 게시 페이지의 파일별 연결·원본 파일명·PDF 본문으로 요청 제품을 확인한다. Raspberry Pi는 공식 포털 제품 검색 GET과 정확히 일치한 카테고리 GET을 최대1회씩 사용해 설계 파일을 보완 발견한다. 제품별 URL/카테고리 ID는 등록하지 않고 크기/HTTPS/공개 IP/허용 호스트/429 경계를 유지한다.
   - Given 유형 표식이 없는 공개 PNG/SVG, When 완성 회로도 후보를 검증, Then 제품명·파일명·검색 제목·HTML title/H1만으로 승인하지 않고 안전하게 조회한 게시 페이지의 회로도 섹션(h2 이하의 하위 제목 포함)·이미지 대체문구·직접 링크 문구가 해당 파일을 회로도로 연결해야 한다. h1 회로도 제목은 해당 파일 경로에도 회로도 표식이 있을 때만 섹션 근거로 사용한다. 단일 이미지와 같은 figure/table의 명시적 figcaption/caption/th 회로도 설명도 인정하되, 복수 이미지나 다른 컨테이너의 설명을 빌려 쓰지 않는다. 다른 파일 링크·다른 섹션·근거 없는 이미지 직접 URL과 부품 배치도는 거절한다. 페이지의 429/외부 장애는 기존 오류 계약으로 유지한다. EDA 원본과 연계된 기존 GitHub 경로·정상 PDF는 유지하고, 이미지 크기나 제조사 여부만으로 거절하지 않는다. 추가 AI 호출 없이 근거 없는 정상 이미지도 보수적으로 제외될 수 있으며, 게시 내용 자체의 진실성까지 보장하지 않는다. SPEC 4절 반영은 조장 검토 제안이다.
   - Given 심벌/부품 라이브러리·핀배치·풋프린트·블록도 유형의 URL 경로 또는 명시적 자료 제목, When 경로에 schematic 표식이 있거나 확장자가 없어도 후보 추출·원본 검사, Then 완성 회로도 후보에서 제외하고 원본을 내려받지 않는다. 같은 도메인의 정상 회로도와 작은 PNG·PDF·SVG는 보존하며 이미지 크기/핀 수만으로 제외하지 않는다. SPEC 4절 반영은 조장 검토 제안이다.
   - 선택 목록은 요청 모델·문서 종류·원본 해시·전체 시트 PNG 변환까지 통과한 후보만 반환한다. 공식·공개 웹은 최대5개, 커뮤니티는 최대24개 저장소에서 검사한 독립 root 후보를 제공한다. 데이터시트·다른 모델·변환 실패·조회 실패 후보는 표시하지 않는다. 같은 검색의 검증 결과를 15분 재사용하며 후보 선택마다 전체 다운로드를 반복하지 않는다. Pico·Pico W·Pico 2·Pico 2 W는 원본 파일과 PDF 본문에서 세대·무선 여부가 일치해야 한다. 정상 후보가 1개이면 그 도면만 표시한다. SPEC 4절 반영은 조장 검토 제안이다.
   - Given 제조사가 지정된 검색(예: Pololu DRV8833), When 모델명만 같은 제조사 미확인 자료를 검사, Then 기존 제조사 별칭 중 요청한 제조사를 뒷받침하는 메타데이터·PDF 본문 근거가 없으면 거절한다. RPi/Raspberry Pi 및 Teensy/PJRC 같은 지원 별칭과 공식 CDN·공개 미러의 실제 제품 근거는 보존한다. 이는 픽셀 의미 분류가 아니며 제조사를 잘못 주장한 문서까지 보증하지 않는다. SPEC 반영은 조장 검토 제안이다.
   - Given 지원 제조사/보드 계열 이름으로 검색(예: Teensy 4.0), When 파일명이 DNMS/noise measuring·weather station·with Arduino처럼 요청하지 않은 프로젝트/용도를 식별, Then 본문·검색 제목에 보드 모델명이 있어도 보드 내부 원본 후보로 승인하지 않고 다운로드 전 거절한다. 파일의 프로젝트 식별어를 검색 대상과 대조하며 특정 DNMS URL/호스트만 차단하지 않는다. 정상 공개 미러·CamelCase·일반 도면/출판 표기·버전·제조사 파일명 별칭·숫자형 자산 이름은 기존 근거/모델 관문과 함께 보존한다. 일반 사용자 정의 프로젝트에는 상용 보드 전용 파일명 제한을 확장하지 않는다. DNMS 자체를 명시적으로 검색하는 경우는 별도 프로젝트 원본 요청으로 취급한다. 모든 픽셀 의미를 판별하는 규칙은 아니며 파일 정체성이 모호한 자료의 잔여 위험은 유지한다. SPEC 반영은 조장 검토 제안이다.
   - 검색어와 원본 메타데이터의 `RPi`·`Raspberry Pi`·지원 한국어 이름은 관련도 계산에서 같은 이름으로 정규화한다. `RPI-PICO`처럼 파일명에 약칭이 있는 도면이 제목만 일치하는 부속 보드들 때문에 후보 5개 상한에서 밀려나지 않아야 한다. 제조사 출처 등급·모델 변형 식별·원본 검증 관문은 유지한다. SPEC 4절의 상세 검색 규칙 반영은 조장 검토 제안이다.
5. 캐시가 채워진 동안 같은 검색·시트를 다시 요청하면 외부 호출과 변환 횟수가 그대로다. 새 인스턴스에서도 유효한 서명 주소가 같은 원본을 가리킨다.

## 구현 상태

| AC | 테스트 | 상태 |
|---|---|---|
| 1 | `tests/projects/test_official_schematic.py`, `tests/projects/test_schematic_render.py` | 공식 페이지 링크 추출·원본 검증 테스트 통과. Adafruit·Pololu·Olimex 원본 직접 조회 통과. 이름 입력부터 끝까지의 재시험은 원격 한도로 미완료 |
| 2 | `tests/projects/test_official_schematic.py`, `tests/api/test_external_circuits.py` | 구현. 공개 웹 이미지의 실조회 확인 |
| 3, 4 | `tests/projects/test_external_schematic.py`, `tests/api/test_external_circuits.py` | 구현. 단위 테스트 확인 |
| 5 | `tests/projects/test_external_schematic.py` | 구현. 단위 테스트 확인 |

## 한계

- 모든 부품에 공개 완성 회로도가 있다는 보장은 없다.
- API 이미지와 로컬 실제 API에는 `kicad-cli`가 없다. KiCad 원본 변환은 배포된 별도 renderer target의 KiCad 10에서만 수행하며, 로컬 Compose는 renderer를 연결하지 않는다. 로컬에서 원격 연결이 없으면 KiCad 원본을 승인하지 않는다. 컨테이너와 실제 화면의 통합 검증은 [작업 기록](../worklog/osc.md)의 2026-11-15 항목을 따른다.
- GitHub 호출 한도: 익명 또는 `GITHUB_TOKEN` 한도를 따른다. 조직 OAuth App 자격 증명을 요청에 연결하는 코드는 없다.
- 설계 시점의 외부 호출 검증(ATtiny85, LM7805 저장소 반환)은 저장소에 원시 기록이 없어 옮기지 않았다.
- Exa의 색인과 공개 접근성에 따라 찾지 못하는 회로도가 있다. 모델명이나 변형을 확신할 수 없으면 다른 회로도로 대신하지 않는다. 회로도 파일명·PDF 본문에서 식별할 수 없는 실제 도면도 제외될 수 있다.
- 게시자가 회로도를 교체하거나 이미지 URL을 닫으면 이전 서명 주소로 재조회할 수 없다. 후보 선택 시 일부 원격 URL은 일시적으로 실패할 수 있다.
- 운영 배포 및 실제 로그인 브라우저 흐름, 전체 평가셋 재측정은 수행하지 않았다. 30건 재시험은 17번째에서 원격 호출 한도에 걸려 중단했으므로 개선 후 성공률은 미확정이다.
