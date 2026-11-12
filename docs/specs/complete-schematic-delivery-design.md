# 공개 프로젝트 완성 회로도 전달 설계

## 목표

사용자가 부품명이나 회로 용도를 입력하면 SojaFit 백엔드가 공개 하드웨어 프로젝트를 찾아 기존 데모 15종과 같은 수준의 완성 회로도 이미지를 제공한다. 완성 회로도는 프로젝트 전체의 부품과 배선이 보이는 schematic을 뜻한다.

데이터시트의 부분 응용 회로, 블록도, 제품 사진, PCB 3D 렌더링과 출처·라이선스·고정 commit을 확인할 수 없는 이미지는 반환하지 않는다. 검증된 완성 회로도가 없으면 결과 없음으로 끝내며 회로를 생성하거나 부분 이미지를 대신 보여주지 않는다.

이번 범위는 백엔드 검색·검증·변환·이미지 응답까지다. 프런트엔드 연결과 화면 변경은 포함하지 않는다.

## 사전 검증 결과

실제 외부 호출로 다음 경로를 확인했다.

- Exa 한 번의 GitHub 제한 검색으로 `tomasr8/attiny85-dev-board`, `gili-yankovitch/attiny85-sample`, `Mimo-Mir/Single-Sided-5V-Power-Supply`를 찾았다.
- GitHub REST API에서 기본 branch, 라이선스, tree와 고정 commit을 확인했다.
- 첫 두 ATtiny85 저장소는 MIT 라이선스, 전체 `schematic.png`와 KiCad 원본을 함께 제공했다.
- LM7805 전원 회로 저장소는 MIT 라이선스, `Docs/schematic.png`와 `.kicad_sch`를 함께 제공했다. 고정 commit의 PNG 20,751바이트를 실제로 받아 기존 데모와 같은 전체 회로도임을 시각 확인했다.
- `UCSIG/attiny85_time_switch`의 전체 schematic PDF를 실제로 받아 1쪽 PNG로 변환했다. PDF 95,763바이트, PNG 149,745바이트, 변환 약 0.67초였다.
- 제조사 데이터시트에서 뽑은 ATtiny85 발진기와 LM7805 응용 회로는 부분 회로이므로 이 기능의 후보에서 제외하기로 확정했다.

이 검증은 공개 저장소에서 전체 schematic PNG/PDF를 찾고 전달하는 경로를 증명한다. 모든 부품에 공개 완성 회로도가 존재한다는 뜻은 아니다. 로컬 개발 환경에는 `kicad-cli`가 없지만 운영 Dockerfile은 KiCad를 설치하므로, KiCad 원본 변환은 컨테이너 검증을 완료 조건에 포함한다.

## 선택한 접근

Exa로 공개 하드웨어 저장소를 찾고, GitHub에서 라이선스·commit·파일 tree를 검증한다. 저장소가 제공하는 전체 schematic PNG/SVG/PDF를 우선 사용하고, 해당 이미지가 없을 때만 KiCad 원본을 서버에서 변환한다.

이 방식은 GitHub Code Search 전용 토큰에 의존하는 방식보다 계정 요구가 적고, 모든 요청을 수동 catalog에 한정하는 방식보다 범위가 넓다. LLM, Mouser, DigiKey와 Nexar는 이 기능에서 호출하지 않는다.

## 완성 회로도 판정

후보 저장소는 다음 조건을 모두 만족해야 한다.

1. Exa 결과가 `github.com/<owner>/<repo>` 형태의 실제 저장소 루트다.
2. GitHub가 식별한 SPDX 라이선스가 있고 허용 목록에 포함된다. 첫 허용 목록은 `MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`, `CC-BY-3.0`, `CC-BY-4.0`, `CC-BY-SA-3.0`, `CC-BY-SA-4.0`, `CERN-OHL-P-2.0`, `CERN-OHL-W-2.0`, `CERN-OHL-S-2.0`, `GPL-2.0-only`, `GPL-2.0-or-later`, `GPL-3.0-only`, `GPL-3.0-or-later`다. `NOASSERTION`과 사용자 정의 라이선스는 자동 결과에서 제외한다.
3. 기본 branch의 정확한 commit SHA와 재귀 tree를 확인할 수 있다.
4. tree에 KiCad 원본(`.kicad_sch` 또는 legacy `.sch`)이 있다.
5. 같은 프로젝트에 전체 schematic으로 명명된 PNG, SVG 또는 PDF가 있거나 KiCad 원본을 변환할 수 있다. 제공 이미지·PDF는 EDA 원본과 같은 디렉터리, 같은 파일 stem 또는 README의 명시적 schematic 링크 중 하나로 연결돼야 한다.
6. `datasheet`, `application-note`, `block-diagram`, `pcb`, `layout`, `render`, `3d`만 나타내는 파일은 제외한다.
7. 이미지나 PDF가 있어도 EDA 원본이 없는 저장소는 자동 판정 후보에서 제외한다.

`schematic`, `circuit`, 프로젝트명과 일치하는 경로를 우선한다. 여러 후보가 동점이면 경로가 짧고 저장소 루트에 가까운 파일을 먼저 사용한다. 이름만으로 완성 여부를 증명할 수 없으므로 EDA 원본 동반을 필수로 한다.

## 검색과 외부 호출

1. 정규화한 사용자 검색어에 `complete schematic`, `KiCad`, `open hardware`를 붙여 Exa를 한 번 호출하고 GitHub 결과만 최대 5개 받는다. Exa 응답은 최대 256KiB까지만 읽는다.
2. 결과 순서대로 최대 3개 저장소만 검사하며 첫 유효 저장소에서 멈춘다.
3. 저장소마다 GitHub REST API metadata(최대 256KiB)에서 라이선스와 기본 branch를 확인하고, commit endpoint(최대 256KiB)에서 head SHA와 tree SHA를 고정한 뒤 재귀 tree(최대 2MiB·5,000개 항목)를 확인한다.
4. 선택한 commit의 `raw.githubusercontent.com` 원본만 받는다. 개별 PNG·SVG는 10MiB, PDF는 20MiB·20쪽, 필요한 저장소 archive는 압축 25MiB·해제 100MiB로 제한한다.
5. 같은 검색어의 성공과 결과 없음은 15분 동안 bounded memory cache에 보관한다.

`GITHUB_TOKEN`이 있으면 인증 요청으로 rate limit을 늘리고, 없으면 공개 익명 API를 사용한다. rate limit이 부족하면 다른 자료로 우회하지 않고 안전한 503과 `Retry-After`를 반환한다. Exa 또는 GitHub 응답 본문과 인증정보는 로그나 공개 오류에 넣지 않는다.

## 변환 우선순위

1. 고정 commit에서 EDA 원본에 대응하는 전체 회로도 PDF를 먼저 확인한다. 페이지 수를 설계 시트 수와 대조하고 모든 페이지를 각각 목표 300 DPI, 시트당 최대 4,000만 픽셀로 렌더링한다.
2. PDF를 사용할 수 없으면 EDA 원본과 연결된 전체 schematic PNG를 검증 후 그대로 사용한다. 다중 시트 EDA 원본에 단일 PNG만 있으면 다음 후보를 확인한다.
3. SVG는 외부 참조·스크립트·이벤트 속성을 거절하고 안전한 SVG만 사용한다.
4. 이미지가 없으면 KiCad 원본을 제한된 임시 디렉터리에 받아 `kicad-cli sch export pdf`로 변환하고 모든 페이지를 PNG로 렌더링한다.
5. 어느 경로도 통과하지 못하면 결과 없음으로 처리한다.

다중 시트 프로젝트는 일부 시트만 반환하면 완성 회로도가 아니므로 전체 시트를 순서대로 제공한다. 원본 비율을 보존하고 각 시트는 독립 PNG 응답으로 만든다. 변환이 끝난 임시 파일은 요청 종료 전에 삭제하며 DB와 영구 파일에는 저장하지 않는다.

## API 계약

### 검색과 이미지 목록

`GET /api/external-circuits/schematics?q=<부품명 또는 용도>`

- 로그인 필요
- `q`: trim 후 2~200자
- 성공: 선택한 프로젝트 하나와 전체 시트 이미지 URL 목록
- 완성 회로도 없음: 404 `SCHEMATIC_NOT_FOUND`
- 검색 비활성·키 없음·GitHub rate limit: 503
- 외부 공급자 장애: 502
- 모든 응답: `Cache-Control: private, no-store`

응답은 화면 연결에 필요한 최소 필드만 제공한다.

```json
{
  "project": "owner/repository",
  "commit": "40자리 commit SHA",
  "license": "MIT",
  "attribution": "owner/repository contributors",
  "repository_url": "https://github.com/owner/repository",
  "source_url": "https://github.com/owner/repository/tree/<commit>",
  "source_file": "hardware/project.kicad_sch",
  "images": [
    {"sheet": 0, "url": "/api/external-circuits/schematics/<signed-token>/0"}
  ]
}
```

### 이미지 바이너리

`GET /api/external-circuits/schematics/{signed_token}/{sheet_index}`

- 로그인 필요
- 서명된 token만 허용하고 임의 외부 URL을 입력받지 않는다.
- PNG 응답에는 `Content-Type: image/png`, `X-Content-Type-Options: nosniff`, `Content-Disposition: inline`을 설정한다.
- token은 저장소, commit, 선택 파일과 만료 시간을 서명한다. 서버 인스턴스가 바뀌어 메모리 cache가 없어도 검증된 고정 원본에서 다시 만들 수 있다.
- cache hit이면 외부 호출과 변환 없이 바로 반환한다.
- sheet 범위 오류, 만료·변조 token은 공개 오류 규약으로 거절한다.

## 캐시와 동시성

- 검색 결과와 변환 PNG는 별도의 bounded TTL LRU cache를 사용한다.
- cache key는 정규화 검색어 또는 `repository + commit + source path + sheet`다.
- 기본 TTL은 15분이며 최대 항목 수와 총 이미지 바이트 상한을 둔다.
- 같은 cache key의 동시 요청은 요청 병합으로 한 번만 외부 호출·변환한다.
- cache는 최적화일 뿐 정본이 아니며 재시작·다중 인스턴스에서 없어져도 서명 token으로 다시 구성한다.
- 검색어, 이미지와 저장소 archive는 DB·대화 상태·로그에 저장하지 않는다.
- HTTP의 `Cache-Control: no-store`는 브라우저·중간 proxy의 저장을 금지한다. 15분 bounded memory cache는 서버 프로세스 내부에서만 사용하는 별도 최적화이며 영구 저장이 아니다.

## 보안과 자원 상한

- 허용 호스트는 Exa API, GitHub API, `raw.githubusercontent.com`과 필요한 GitHub archive host로 고정한다.
- 외부 URL은 HTTPS, 공개 IP, 표준 포트, 사용자정보 없음 조건을 만족해야 한다.
- redirect를 자동으로 따르지 않고 각 hop의 scheme·host·IP를 다시 검증한다.
- 응답은 streaming으로 읽으며 선언 길이와 실제 누적 바이트 상한을 모두 확인한다.
- 저장소 archive, 개별 이미지, PDF, 페이지 수, SVG node 수, 변환 시간과 출력 픽셀 수에 각각 상한을 둔다. 한 시트의 출력은 40메가픽셀을 넘지 않는다.
- PDF는 `%PDF-`, PNG는 PNG signature, SVG는 안전한 XML root를 확인한다.
- archive는 절대 경로, `..`, symlink, 중복 경로와 압축 폭탄을 거절한다.
- subprocess는 shell 없이 고정 인자 목록, 제한 시간, 제한된 임시 디렉터리와 최소 환경으로 실행한다.
- 외부 문서와 저장소 내용은 명령으로 해석하지 않는다.

## 구성 요소

- `backend/projects/external_circuit_search.py`: Exa 검색의 GitHub 저장소 후보 정제와 공통 안전 URL 검사
- 새 `backend/projects/external_schematic.py`: GitHub metadata/tree 확인, 라이선스·commit·후보 선택, 안전한 다운로드, 변환과 cache
- `backend/projects/schematic.py`: 기존 KiCad subprocess와 SVG 안전성 경계 중 재사용 가능한 부분 사용
- `backend/api/external_circuits.py`: 목록과 이미지 바이너리 endpoint, 인증·입력·공개 오류·응답 header
- `backend/main.py`: 기존 external-circuits router와 공통 no-store 정책 유지
- `pyproject.toml`·`uv.lock`: PDF 렌더링에 필요한 최소 런타임 의존성만 운영 dependencies로 이동
- `.env.example`: 선택적 `GITHUB_TOKEN`과 기능 상한 설명
- 관련 폴더 문서와 OpenAPI 계약 테스트

기존 Exa 근거 답변 endpoint는 이번 설계에서 호출하지 않는다. 삭제는 별도 승인 없이는 수행하지 않는다.

## 검증 전략

### 단위 테스트

- Exa 결과에서 저장소 루트만 허용하고 reserved·파일·issue URL을 거절한다.
- GitHub 라이선스 없음, 비허용 라이선스, EDA 원본 없음, 부분 회로·PCB 이미지만 있는 저장소를 제외한다.
- 고정 commit의 PNG·안전 SVG·다중 페이지 PDF·KiCad fallback을 각각 PNG 목록으로 만든다.
- URL, redirect, MIME, magic bytes, 크기, 페이지, archive path와 subprocess 상한을 위반하면 외부 원문을 노출하지 않고 실패한다.
- signed token의 정상·만료·변조·sheet 범위를 검증한다.
- cache hit, TTL 만료, LRU 퇴출, byte 상한과 동시 요청 병합을 검증한다.
- 파일·DB·대화 상태와 로그에 검색어·이미지·외부 본문을 저장하지 않는 경계를 검증한다.

### API 테스트

- 로그인, query 경계, 결과 없음 404, 502·503 안전 오류, no-store를 확인한다.
- manifest의 모든 이미지 URL이 실제 PNG endpoint와 연결된다.
- PNG 응답의 content type, `nosniff`, inline과 비캐시 header를 확인한다.
- 기존 `/api/external-circuits/search`와 `/answer` 계약을 회귀 검증한다.

### 실제 통합 검증

- `ATtiny85`가 MIT 저장소의 전체 개발 보드 schematic을 반환한다.
- `LM7805 power supply`가 MIT 저장소의 전체 전원 회로 schematic을 반환한다.
- 부분 응용 회로만 있는 검색은 결과로 채택하지 않는다.
- 동일 검색 두 번째 요청에서 Exa·GitHub·변환 호출이 발생하지 않는지 계측한다.
- 운영 Docker를 빌드해 `kicad-cli`와 PDF 렌더러가 실제로 동작하는지 확인한다.
- 전체 backend pytest와 `git diff --check`를 통과한다. 프런트 테스트와 빌드는 이번 백엔드 전용 변경의 필수 검증이 아니다.

## 완료 기준

- 사용자가 부품명 또는 용도를 입력하면 라이선스와 고정 commit이 확인된 공개 프로젝트의 완성 회로도만 받을 수 있다.
- 데이터시트 부분 회로, 블록도, PCB·제품 이미지는 반환되지 않는다.
- 다중 시트 프로젝트는 전체 시트를 순서대로 제공한다.
- 찾지 못한 경우 추측이나 대체 이미지를 만들지 않고 명확한 404를 반환한다.
- LLM, Mouser, DigiKey, Nexar와 DB를 사용하지 않는다.
- 첫 요청 외에는 bounded TTL cache로 외부 호출과 변환을 줄인다.
- 보안·자원 상한, 실제 ATtiny85·LM7805 통합 검증과 전체 backend 회귀 검사가 통과한다.
