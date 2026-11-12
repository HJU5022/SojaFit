# 공개 프로젝트 완성 회로도

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 정본(공개 프로젝트 완성 회로도 API). 경로·오류 코드의 제품 수준 목록은 [SPEC.md](../../SPEC.md)
- 관련 문서: [backend/projects/PROJECTS.md](../../backend/projects/PROJECTS.md)

## Why

회로 설계자가 부품명이나 용도를 입력해 실제 공개 보드에서 부품과 배선을 함께 확인한다. 측정 항목은 반환된 전체 시트 수와 동일 검색의 추가 외부 호출 수다.

## Goal

- 검증한 프로젝트 하나의 전체 시트, 출처, 라이선스, 커밋을 반환한다.
- 15분 동안 같은 검색의 외부 호출을 재사용한다.
- 적용 범위는 백엔드 API다. 프런트엔드 화면은 범위 밖이다.
- 범위 밖: 데이터시트의 부분 응용 회로, 블록도, 제품 사진, PCB 렌더링 반환. 검증된 완성 회로도가 없을 때 회로 생성·대체 이미지. LLM·Mouser·DigiKey·Nexar·DB 사용.

## What

로그인한 사용자가 이름을 입력하면 서버가 공개 저장소를 찾고 KiCad 원본과 시트 구성을 확인한다.

| 상황 | 응답 | 근거 |
|---|---|---|
| 성공 | 200, 프로젝트와 `images` 배열 | `backend/api/external_circuits.py:59-73` |
| 적합한 프로젝트 없음, 시트 번호 음수, 만료·변조된 토큰, 시트 번호 범위 밖 | 404 `SCHEMATIC_NOT_FOUND` | `backend/api/external_circuits.py:49,82`, `backend/projects/external_schematic.py:173-185` |
| 검색어 2자 미만·200자 초과 | 422 | `backend/api/external_circuits.py:62` |
| 공급자 장애 | 502 | `backend/api/external_circuits.py:56` |
| 기능 비활성·설정 누락(서명 키 포함) | 503 | `backend/projects/external_schematic.py:36-39,212-216` |
| GitHub 호출 한도 | 503, `Retry-After` 1~3600초 | `backend/projects/schematic_source.py:48`, `backend/api/external_circuits.py:51` |

기능 활성 조건: `DEMO_MODE=0`, `EXA_WEB_SEARCH_ENABLED=1`, `EXA_API_KEY` 값 있음, `AUTH_SECRET` 32바이트 이상(`backend/projects/external_schematic.py:212-216,36-39`).

## How

### API

| 경로 | 동작 | 근거 |
|---|---|---|
| `GET /api/external-circuits/schematics?q=` | 프로젝트(`project`, `commit`, `license`, `attribution`, `repository_url`, `source_url`, `source_file`)와 순서가 있는 `images`(`sheet`, `url`) 반환. `q`는 trim 후 2~200자 | `backend/api/external_circuits.py:27-73` |
| `GET /api/external-circuits/schematics/{signed_token}/{sheet_index}` | 같은 로그인 세션에서 PNG 반환. 임의 외부 URL은 받지 않는다 | `backend/api/external_circuits.py:75-86` |

두 경로 모두 로그인이 필요하다. 응답 헤더는 `Cache-Control: private, no-store`다. PNG는 `X-Content-Type-Options: nosniff`, `Content-Disposition: inline`을 더한다.

### 검색과 검증

| 단계 | 내용 | 근거 |
|---|---|---|
| 1. 후보 검색 | 검색어에 `complete schematic KiCad open hardware GitHub`를 붙여 Exa를 1회 호출하고 `github.com` 저장소 루트 최대 5개를 받는다. 응답은 256 KiB까지 읽는다 | `backend/projects/external_circuit_search.py:125-128` |
| 2. 후보 검사 | 앞의 3개 저장소만 검사하고 첫 유효 프로젝트에서 멈춘다 | `backend/projects/external_schematic.py:149` |
| 3. 저장소 검증 | GitHub 메타데이터의 SPDX 라이선스가 허용 목록(`ALLOWED_LICENSES`, 16종)에 있고 비공개가 아니어야 한다. 기본 브랜치 head 커밋·트리 SHA(40자리)를 고정하고 재귀 트리를 읽는다. `NOASSERTION`·사용자 정의 라이선스는 제외 | `backend/projects/schematic_source.py:6-11`, `backend/projects/schematic_discovery.py:352-367` |
| 4. 원본 확인 | 트리에 `.kicad_sch` 또는 `.sch`가 1~20개 있어야 한다. 원본 파일 내용(파일당 4 MiB, 합계 12 MiB)을 읽어 시트 구성을 해석한다. 배치된 심볼 2개 이상과 배선이 있어야 한다. 검색어가 부품 값이나 README와 맞아야 한다 | `backend/projects/schematic_discovery.py:368-404` |
| 5. 이미지 후보 | PDF, PNG, SVG 파일 중 이름이 전체 회로도를 가리키고(데이터시트·응용 노트·블록도·PCB·레이아웃·렌더·3D 등은 제외) EDA 원본과 같은 디렉터리·같은 파일 stem·README 링크 중 하나로 연결된 것만 쓴다. 시트가 여러 개이면 PDF만 쓴다 | `backend/projects/schematic_discovery.py:25,409-450` |
| 6. 변환 우선순위 | PDF, PNG, SVG, KiCad 원본 순. 앞 순위가 검증에 실패하면 다음으로 넘어간다. 모든 후보가 탈락하면 다음 저장소를 검사하고, 저장소가 모두 탈락하면 404 | `backend/projects/schematic_discovery.py:451-454`, `backend/projects/external_schematic.py:148-159` |

- 제공한 PNG·PDF 이미지는 고정 커밋의 `raw.githubusercontent.com` 원본에서 받는다.
- PDF는 모든 페이지를 목표 300 DPI로 PNG 렌더링한다. 시트당 출력은 4,000만 픽셀 이내로 줄인다(`backend/projects/schematic_render.py:36-37,150-157`).
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
| Exa 응답 | 256 KiB | `backend/projects/external_circuit_search.py:128` |
| GitHub 저장소·커밋 응답 | 각 256 KiB | `backend/projects/schematic_discovery.py:352` |
| GitHub 재귀 트리 응답 | 2 MiB, 항목 5,000개 | `backend/projects/schematic_discovery.py:111,368` |
| 원본 EDA 파일 | 파일당 4 MiB, 합계 12 MiB, 최대 20개 | `backend/projects/schematic_discovery.py:370,383-385` |
| PNG·SVG 이미지 | 10 MiB | `backend/projects/schematic_render.py:30` |
| PDF | 20 MiB, 20쪽 | `backend/projects/schematic_render.py:31,35` |
| 저장소 압축본 | 압축 25 MiB, 해제 100 MiB, 항목 5,000개 | `backend/projects/schematic_render.py:32-34` |
| 시트 수 | 20 | `backend/projects/schematic_render.py:35` |
| 시트당 출력 | 4,000만 픽셀 | `backend/projects/schematic_render.py:36` |
| 변환 subprocess | 제한 시간 30초 | `backend/projects/schematic.py:8` |
| 외부 요청 | HTTPS, 공개 IP, 표준 포트, 사용자정보 없음. 허용 호스트 `api.github.com`, `raw.githubusercontent.com`, `codeload.github.com`. 리다이렉트는 hop마다 재검증, 최대 4회 | `backend/projects/schematic_discovery.py:21-23,50-63` |
| GitHub 인증 | `GITHUB_TOKEN`이 있으면 API 호스트 요청에만 붙인다. 없으면 익명 | `backend/projects/schematic_discovery.py:61-63` |

## AC

1. 공개 개발 보드의 소스와 라이선스가 확인된 상태에서 검색하면, 각 시트 URL이 원본 비율의 PNG를 제공한다.
2. 후보가 데이터시트나 PCB 이미지만 제공하면 다음 저장소를 검사하고, 모든 후보가 탈락하면 `SCHEMATIC_NOT_FOUND`를 반환한다.
3. 캐시가 채워진 동안 같은 검색·시트를 다시 요청하면 외부 호출과 변환 횟수가 그대로다. 새 인스턴스에서도 유효한 서명 주소가 같은 원본을 가리킨다.

## 구현 상태

| AC | 테스트 | 상태 |
|---|---|---|
| 1 | `tests/projects/test_schematic_render.py`, `tests/projects/test_external_schematic.py` | 구현. 개별 테스트와 AC 문장의 대응은 대조하지 않음 |
| 2 | `tests/projects/test_schematic_discovery.py`, `tests/api/test_external_circuits.py` | 구현. 대응 미대조 |
| 3 | `tests/projects/test_external_schematic.py` | 구현. 대응 미대조 |
| 검색 후보 정제 | `tests/projects/test_external_circuit_search.py` | 구현 |

## 한계

- 모든 부품에 공개 완성 회로도가 있다는 보장은 없다.
- 로컬 개발 환경에는 `kicad-cli`가 없다. KiCad 원본 변환 경로는 운영 이미지에서만 실행된다. 컨테이너 검증 결과는 이 저장소에 기록이 없다(미확인).
- GitHub 호출 한도: 익명 또는 `GITHUB_TOKEN` 한도를 따른다. 조직 OAuth App 자격 증명을 요청에 연결하는 코드는 없다.
- 설계 시점의 외부 호출 검증(ATtiny85, LM7805 저장소 반환)은 저장소에 원시 기록이 없어 옮기지 않았다.
- `ATtiny85`·`LM7805` 실검색 결과와 Exa·GitHub 호출 횟수 계측은 미확인.
