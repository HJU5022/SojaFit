# 공개 프로젝트 완성 회로도

- 상태: 현행
- 기준일: 2026-11-13
- 기준 커밋: STH 3d8edff의 로컬 수정(미커밋)
- 정본 여부: 정본(공개 프로젝트 완성 회로도 API). 경로·오류 코드의 제품 수준 목록은 [SPEC.md](../../SPEC.md)
- 관련 문서: [backend/projects/PROJECTS.md](../../backend/projects/PROJECTS.md)

## Why

회로 설계자가 부품명이나 용도를 입력해 실제 공개 보드에서 부품과 배선을 함께 확인한다. 측정 항목은 반환된 전체 시트 수와 동일 검색의 추가 외부 호출 수다.

## Goal

- 이름으로 발견한 공개 회로도 파일의 시트, 게시 페이지, 원본 URL, 출처와 확인 가능한 라이선스를 반환한다. 공개 저장소가 출처이면 커밋도 반환한다.
- 15분 동안 같은 검색의 외부 호출을 재사용한다.
- 적용 범위는 백엔드 API와 작업대 원본 회로도 창이다.
- 범위 밖: 데이터시트의 부분 응용 회로, 블록도, 제품 사진, PCB 렌더링 반환. 검증된 완성 회로도가 없을 때 회로 생성·대체 이미지. LLM·Mouser·DigiKey·Nexar·DB 사용.

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

### API

| 경로 | 동작 | 근거 |
|---|---|---|
| `GET /api/external-circuits/schematics?q=&source_url=` | 이름으로 찾은 회로도와 순서가 있는 `images`(`sheet`, `url`), 다른 검색 후보 `choices`를 반환한다. `source_url`은 선택 사항이며 같은 검색의 Exa 후보에 포함된 URL일 때만 허용한다. `q`는 trim 후 2~200자 | `backend/api/external_circuits.py` |
| `GET /api/external-circuits/schematics/{signed_token}/{sheet_index}` | 같은 로그인 세션에서 PNG 반환. 임의 외부 URL은 받지 않는다 | `backend/api/external_circuits.py:75-86` |

두 경로 모두 로그인이 필요하다. 응답 헤더는 `Cache-Control: private, no-store`다. PNG는 `X-Content-Type-Options: nosniff`, `Content-Disposition: inline`을 더한다.

### 검색과 검증

| 단계 | 내용 | 근거 |
|---|---|---|
| 1. 후보 검색 | 회로도 이름으로 Exa 공개 웹을 1회 검색하고, 제조사를 식별할 수 있으면 해당 공식 도메인으로 보강 검색한다. 사전 지정 모델 URL 없이 PDF·PNG·SVG 및 게시 페이지의 링크 글자·제목·이미지 설명에서 회로도 파일을 찾는다. 응답은 512 KiB 상한 | `backend/projects/external_circuit_search.py` |
| 2. 이름·이미지 확인 | 회로도 표식이 없는 사진·PCB·배선·데이터시트와 모델·변형이 다른 후보, 축약 도면을 제외한다. 검색어와 제목·게시 페이지·원본 URL 및 PDF 본문을 대조한다. 이름 일치를 우선하고, 제조사 공식 회로도 이미지가 안내서 PDF보다 앞선다 | `backend/projects/external_circuit_search.py`, `backend/projects/schematic_render.py` |
| 3. 출처 표시 | 확인된 제조사 공식 도메인의 게시 페이지와 해당 제조사 원본의 연결을 확인하면 `manufacturer_official`, 2등급으로 표시한다. 그 밖의 공개 웹 자료는 `public_web`, 등급 미지정으로 표시한다. 공개 GitHub 저장소 검증 경로는 후보가 없거나 무효일 때 계속 사용할 수 있다 | `backend/projects/external_circuit_search.py`, `backend/projects/external_schematic.py` |
| 4. 파일 검증·변환 | 각 후보의 HTTPS·공개 IP·형식·크기를 제한하고 연결 IP를 DNS 검증 결과에 고정한다. 모델 식별과 원본 SHA-256을 확인해 PNG로 변환한다. 다중 페이지 PDF는 목차를 제외한 회로도 표시 페이지만 반환한다. 일시적인 원본 요청 오류는 검색 전체에서 최대 1회 재시도하며, 한 후보가 호출 제한에 걸리면 다음 후보를 검사한다 | `backend/projects/schematic_discovery.py`, `backend/projects/schematic_render.py`, `backend/projects/external_schematic.py` |
| 5. 결과 선택 | 첫 유효 후보와 함께 최대 5개의 이름·출처 후보를 전달한다. 사용자가 다른 후보를 선택하면 서버가 같은 검색 결과에 포함된 URL인지 검사한 후 파일을 다시 검증한다 | `backend/projects/external_schematic.py`, `frontend/src/components/Schematic.tsx` |

- 공개 GitHub 저장소 후보의 PNG·PDF 이미지는 고정 커밋의 `raw.githubusercontent.com` 원본에서 받는다. 제조사 페이지가 연결한 공식 GitHub 파일은 해당 원본 URL에서 받으며, 재조회 시 SHA-256이 달라지면 버린다. 그 밖의 공개 웹 후보는 검색으로 확인한 원본 URL에서 받는다.
- 제조사 도메인 보강 검색은 검색어에서 식별한 Adafruit·SparkFun·Seeed·Arduino·Pololu·Olimex·Raspberry Pi·PJRC의 공식 도메인으로 제한한다. 제조사 페이지의 GitHub 자료는 허용한 공식 조직의 직접 링크만 원본으로 취급한다.
- PDF는 전체 회로도 파일의 시트를 목표 300 DPI로 변환한다. 여러 페이지의 일반 안내서는 회로도 표시 페이지를 식별할 때만 그 페이지를 반환한다. 시트당 출력은 4,000만 픽셀 이내다.
- KiCad 원본은 저장소 압축본을 임시 디렉터리에 풀어 `kicad-cli`로 PDF로 내보낸 뒤 같은 방식으로 렌더링한다. 운영 이미지는 `kicad`를 설치한다(`backend/projects/schematic_render.py:194-310`, `Dockerfile:16`).
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
| 원본 EDA 파일 | 파일당 4 MiB, 합계 12 MiB, 최대 20개 | `backend/projects/schematic_discovery.py:370,383-385` |
| PNG·SVG 이미지 | 10 MiB | `backend/projects/schematic_render.py:30` |
| PDF | 20 MiB, 20쪽 | `backend/projects/schematic_render.py:31,35` |
| 저장소 압축본 | 압축 25 MiB, 해제 100 MiB, 항목 5,000개 | `backend/projects/schematic_render.py:32-34` |
| 시트 수 | 20 | `backend/projects/schematic_render.py:35` |
| 시트당 출력 | 4,000만 픽셀 | `backend/projects/schematic_render.py:36` |
| 변환 subprocess | 제한 시간 30초 | `backend/projects/schematic.py:8` |
| 외부 요청 | HTTPS, 공개 IP, 표준 포트, 사용자정보 없음. 각 후보에서 검증한 호스트와 공개 IP로 연결한다. 리다이렉트는 hop마다 재검증, 최대 4회 | `backend/projects/schematic_discovery.py` |
| GitHub 인증 | `GITHUB_TOKEN`이 있으면 API 호스트 요청에만 붙인다. 없으면 익명 | `backend/projects/schematic_discovery.py:61-63` |

## 화면

작업대의 원본 회로도 창(`frontend/src/components/Schematic.tsx`)에서 사용자가 이름을 입력하고 검색 버튼을 누르면 이 API를 호출한다. 여러 출처가 검색되면 후보 목록에서 다른 원본을 선택할 수 있다.

- 검색어 칸의 처음 값은 프로젝트 이름이다. 프로젝트 응답에 넷리스트 제목·보드 이름이 없다. 사용자가 고칠 수 있다.
- 검색은 버튼을 눌러야 보낸다(자동 호출 없음). 같은 검색어는 5분 동안 다시 보내지 않는다. 검색 중에는 버튼이 꺼진다.
- 검색어가 2자 미만이거나 200자 초과이면 버튼이 꺼지고 규칙 문구를 보인다. API를 부르지 않는다.
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
   - 선택 목록은 요청 모델·문서 종류·원본 해시·전체 시트 PNG 변환까지 통과한 후보만 최대 5개 반환한다. 데이터시트·다른 모델·변환 실패·조회 실패 후보는 표시하지 않는다. 같은 검색의 검증 결과를 15분 재사용하며 후보 선택마다 전체 다운로드를 반복하지 않는다. Pico·Pico W·Pico 2·Pico 2 W는 원본 파일과 PDF 본문에서 세대·무선 여부가 일치해야 한다. 정상 후보가 1개이면 그 도면만 표시한다. SPEC 4절 반영은 조장 검토 제안이다.
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
- 로컬 개발 환경에는 `kicad-cli`가 없다. KiCad 원본 변환 경로는 운영 이미지에서만 실행된다. 컨테이너 검증 결과는 이 저장소에 기록이 없다(미확인).
- GitHub 호출 한도: 익명 또는 `GITHUB_TOKEN` 한도를 따른다. 조직 OAuth App 자격 증명을 요청에 연결하는 코드는 없다.
- 설계 시점의 외부 호출 검증(ATtiny85, LM7805 저장소 반환)은 저장소에 원시 기록이 없어 옮기지 않았다.
- Exa의 색인과 공개 접근성에 따라 찾지 못하는 회로도가 있다. 모델명이나 변형을 확신할 수 없으면 다른 회로도로 대신하지 않는다. 회로도 파일명·PDF 본문에서 식별할 수 없는 실제 도면도 제외될 수 있다.
- 게시자가 회로도를 교체하거나 이미지 URL을 닫으면 이전 서명 주소로 재조회할 수 없다. 후보 선택 시 일부 원격 URL은 일시적으로 실패할 수 있다.
- 운영 배포 및 실제 로그인 브라우저 흐름, 전체 평가셋 재측정은 수행하지 않았다. 30건 재시험은 17번째에서 원격 호출 한도에 걸려 중단했으므로 개선 후 성공률은 미확정이다.
