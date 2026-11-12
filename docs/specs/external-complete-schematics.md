# 공개 프로젝트 완성 회로도

## Why

회로 설계자가 부품명이나 용도를 입력해 실제 공개 보드에서 부품과 배선을 함께 확인한다. 측정 항목은 반환된 전체 시트 수와 동일 검색의 추가 외부 호출 수다.

## Goal

검증한 프로젝트 하나의 전체 시트, 출처, 라이선스, 커밋을 반환한다. 15분 동안 같은 검색의 외부 호출을 재사용한다. 적용 범위는 백엔드 API다.

## What

로그인한 사용자가 이름을 입력하면 서버가 공개 저장소를 찾고 KiCad 원본과 시트 구성을 확인한다. 적합한 프로젝트가 없으면 404, 잘못된 검색어는 422, 공급자 장애는 502, 비활성화·설정 누락·호출 한도는 503이다.

## How

- `GET /api/external-circuits/schematics?q=ATtiny85`는 프로젝트와 순서가 있는 `images` 배열을 반환한다. 각 URL을 같은 로그인 세션으로 열면 PNG를 받는다.
- Exa 검색 1회로 최대 5개 후보를 찾고 앞의 3개까지 검사한다. 검증한 원본은 고정 커밋으로 읽는다. 시트가 여러 개인 회로는 모든 시트를 확인한다.
- 회로 설계 파일에 대응하는 전체 회로도 PDF가 있으면 먼저 사용한다. 사용자에게 제공하는 PNG는 PDF에서 목표 300 DPI로 렌더링하며, 큰 도면은 시트당 4,000만 픽셀 이내로 해상도를 조정한다. PDF가 없거나 원본 검증에 실패하면 다른 회로도 자료를 확인한다.
- 원본과 PNG는 요청 중 메모리 또는 변환용 임시 디렉터리에서 처리한다. 이미지 응답은 `private, no-store`이고 서버 내부 캐시는 15분이다.
- 현대 KiCad 원본은 PDF로 내보내 모든 시트를 PNG로 변환할 수 있다. 구형 `.sch`는 해당 프로젝트가 제공한 전체 PNG·SVG·PDF를 확인할 수 있을 때 지원한다. 검증에 사용한 KiCad 9.0.2가 구형 원본을 직접 내보낼 때 배치된 심볼을 누락한 사례가 있었다.
- 설정과 자원 상한은 [승인 설계](complete-schematic-delivery-design.md)를 따른다.

### 운영 준비 · 팀 GitHub 조직의 OAuth App 등록

소자핏 백엔드는 회로도 원본을 확인할 때 외부 공개 저장소의 커밋과 파일 목록을 조회한다. 조직 소유 OAuth App의 Client ID와 Client Secret으로 공개 데이터를 조회하면 일반 조직 기준 앱 하나에 시간당 5,000회의 REST API 요청 한도가 적용된다. 부품 검색 한 건에 여러 요청을 사용할 수 있다. [GitHub의 OAuth App 호출 한도](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api#primary-rate-limit-for-oauth-apps)

**조직 관리자에게 요청할 작업**

1. 팀 조직의 **Settings → Developer settings → OAuth Apps → New OAuth App**에서 등록한다. 첫 등록이면 **Register a new application**을 선택한다.
2. 앱 이름은 예를 들어 `SojaFit Circuit Search`로 입력하고, **Homepage URL**에는 팀의 공개 서비스 주소를 넣는다. 필수 **Authorization callback URL**에는 팀이 관리하는 HTTPS 주소를 입력한다. 이번 공개 데이터 조회는 서버에서 인증하므로 사용자 로그인이나 콜백 호출이 발생하지 않는다. **Register application**을 누르고 소유자가 팀 조직인지 확인한다. [GitHub 앱 등록 안내](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app)
3. 앱 설정에서 **Generate a new client secret**을 선택한다. Client ID와 Client Secret을 백엔드 배포용 Secret Manager에 전달하고, PR에는 조직명·앱 이름·등록 여부만 남긴다.

**백엔드 담당자 인계** · 현재 회로도 조회 코드는 `GITHUB_TOKEN`을 읽으며, 값이 비어 있으면 익명으로 요청한다. 앱 등록 후에는 별도 변경으로 `api.github.com` 요청에 앱 자격 증명을 연결해야 한다. 연결 후 팀 외부의 공개 회로 저장소로 검색하여 PNG 반환과 GitHub 응답의 `X-RateLimit-Limit`, `X-RateLimit-Remaining`을 확인한다. [현재 GitHub 요청 코드](../../backend/projects/schematic_discovery.py)

**이 기능 PR의 ‘리뷰 포인트’에 붙여 넣을 문구**

> 조직 관리자께서는 공개 회로도 조회용 OAuth App을 팀 GitHub 조직 명의로 등록하고, 앱 자격 증명을 백엔드 배포용 Secret Manager에 보관해 주세요. 이 PR에는 등록 절차를 담았습니다. 등록 여부와 앱 이름을 알려 주시면 백엔드 담당자가 앱 인증 연결과 PNG 조회를 후속으로 검증합니다.

## AC

1. 공개 개발 보드의 소스와 라이선스가 확인된 상태에서 검색하면, 각 시트 URL이 원본 비율의 PNG를 제공한다.
2. 후보가 데이터시트나 PCB 이미지만 제공하면 다음 저장소를 검사하고, 모든 후보가 탈락하면 `SCHEMATIC_NOT_FOUND`를 반환한다.
3. 캐시가 채워진 동안 같은 검색·시트를 다시 요청하면 외부 호출과 변환 횟수가 그대로다. 새 인스턴스에서도 유효한 서명 주소가 같은 원본을 가리킨다.
