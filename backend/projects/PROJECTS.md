# projects

## 역할
- 넣는 것: 소유 사용자 조건이 포함된 프로젝트 SQL과 공개 DTO. 단일 catalog의 데모 15종 복제, 검증된 15종 회로도, Task 5의 제한된 KiCad export 정규화.
- 넣지 않는 것: HTTP 라우트·multipart 수신(`backend/api/`), 원본 넷리스트·가격 저장, D5 실행.
- 담당: 서비스·운영

## 파일
- `catalog.py` — `catalog.json`의 안전한 ID·이름·저장소 내부 연결 경로를 검증하고 immutable catalog를 제공한다.
- `PROJECTS.md` — 이 문서
- `__init__.py` — 패키지 표시
- `models.py` — 목록 메타데이터와 정규화 연결 정보를 포함한 상세 DTO
- `netlist.py` — `normalize_netlist(bytes) -> NormalizedCircuit`. 불변 `connections`(parts/nets), SHA-256, 부품 ref tuple만 반환. 원본·경로·파일 핸들 없음
- `repository.py` — `create_demo`, `create_upload`, `list_owned`, `get_owned`, `rename_owned`, `delete_owned`. 모든 조회·변경·삭제에 `user_id` 조건 적용. 관리자 예외 없음
- `visuals.py` — `load_demo_visuals()`가 데모 15종 catalog를 한 번 읽고 immutable·extra-forbid metadata, HTTPS 출처, hex commit·원본/배포 hash, 고정 PNG 경로·존재·배포 hash를 검사한다. 누락·추가 ID나 손상 자산은 명시적 예외다. 외부 다운로드 없음.
- `external_circuit_search.py` — Exa 결과에서 안전한 GitHub 저장소 루트 후보만 정제한다.
- `external_schematic.py` — 저장소 출처·라이선스·commit을 확인하고 전체 회로도 시트를 임시 변환·캐시한다.
- `schematic.py` — KiCad CLI PDF export의 shell 없는 실행 경계를 제공한다.
- `schematic_discovery.py` — GitHub tree에서 EDA 원본과 연결된 전체 회로도 자산을 찾는다.
- `schematic_render.py` — PDF/SVG/PNG 시트를 제한된 크기와 해상도로 PNG로 렌더링한다.
- `schematic_source.py` — 검증된 외부 회로도 source DTO를 제공한다.

`auth.connection()`과 `db/018_projects.sql`을 사용한다. 생성은 프로젝트·회로를 한 트랜잭션으로 저장하고 삭제는 FK cascade를 사용한다. 데모 `source_sha256`은 기존 `connections.json` 바이트의 SHA-256이며 `parser_version`은 `demo-connections-v1`이다. 목록에는 연결 정보를 싣지 않고 상세·생성·이름 변경 결과에만 싣는다. 데이터 출처와 라이선스는 [CIRCUITS.md](../../data/circuits/CIRCUITS.md)를 따른다.

`create_upload(user_id, name, *, connections, source_sha256, parser_version)`에는 정규화 데이터만 전달한다. 업로드 원본은 5 MiB 이하, UTF-8 strict이며 decode 전에 SHA-256을 계산한다. 괄호·문자열·atom을 합쳐 500,000 token, root 포함 깊이 64, components/nets 각각 100,000개를 넘으면 거절한다. export/components/nets 및 ref/value/footprint/code/name/node의 ref/pin만 보존한다. 메타데이터는 문법·상한만 검사하고 버린다. 문자열 escape는 `\"`, `\\`, `\n`, `\r`, `\t`만 허용하며 unbalanced/trailing 구조·중복/누락 필드·알 수 없는 node ref는 거절한다. 파서 버전은 `kicad-export-v1`이다.

NUL은 quoted/unquoted 및 메타데이터를 포함한 입력 전체에서 거절한다. net code는 공개 KiCad 5종과 같이 ASCII 양의 정수의 표준 표기(`[1-9][0-9]*`)만 허용하고 문자열로 보존한다. 0/음수/소수/부호/지수/앞자리 0/비ASCII 숫자는 거절하며 code는 넷마다 유일해야 한다. Python 정수 변환은 하지 않아 큰 숫자 문자열의 변환 오류가 생기지 않는다.
