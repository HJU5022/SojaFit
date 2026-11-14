# projects

## 역할
- 이 폴더: 사용자 소유 프로젝트·정규화 회로 저장소와 공개 DTO, 데모 회로 catalog 검증, 외부 공개 회로도 검색·변환.
- 넣는 것: 소유 사용자 조건이 붙은 프로젝트 SQL(`repository.py`), 단일 catalog(`data/circuits/catalog.json`)의 데모 복제와 회로도 출처 검증, 제한된 KiCad export 정규화(`netlist.py`), 외부 회로도의 검색 후보 정제·원본 확인·PNG 변환.
- 넣지 않는 것: HTTP 라우트와 multipart 수신(`backend/api/`), 원본 넷리스트·가격 저장, 분석 실행(`backend/multi_agent/`).
- 담당: 서비스·운영

저장소는 `auth.connection()`과 `db/020_service_baseline.sql`·`db/031_circuit_versions.sql`의 표를 쓴다. 모든 조회·변경·삭제에 `user_id` 조건이 붙고 관리자 예외는 없다. 빈 프로젝트는 v0, 데모 복제·처음 업로드는 v1이다. 기존 프로젝트에 업로드하면 프로젝트 잠금 아래 새 불변 버전과 새 대화를 한 트랜잭션으로 저장한다. `circuits`는 최신 버전이고 `project_circuit_versions`는 과거 회로를 보존한다. 삭제는 FK cascade를 쓴다. 업로드 정규화의 크기·깊이·개수 상한과 파서 버전은 `netlist.py` 상수(`MAX_BYTES`, `MAX_DEPTH`, `MAX_TOKENS`, `MAX_COMPONENTS`, `MAX_NETS`, `PARSER_VERSION`)가 정본이다. 데모 회로의 출처와 라이선스는 [CIRCUITS.md](../../data/circuits/CIRCUITS.md)를 따른다.

외부 다이오드 회로 검색은 BOM 색인과 독립 GitHub 검색 경로를 함께 사용하며 저장소 후보를 최대 24개 검증한다. discovery는 최대 128파일·파일당 4MiB·총 25MiB까지 현대 KiCad 파일을 먼저 읽는다. 렌더링은 검증한 선택 계층만 고정 commit에서 직접 다운로드하며 파일당 10MiB·총 25MiB·최대 20시트로 제한한다. 검색과 무관한 다른 프로젝트의 손상 파일을 격리하되 선택한 계층의 누락·순환은 거부한다. 품번은 실제 배치 심벌에서 확인하고, 구형 KiCad의 instance 값은 배치 UUID·참조번호가 일치할 때만 사용한다. 사용자 정의 다이오드는 설명과 양극/음극 핀 구조를 함께 검사한다. 저장소의 여러 완전한 회로가 일치하면 서로 섞지 않고 고정 commit·root별 선택 URL을 제공한다. 검증한 후보 목록은 15분 캐시하고 선택한 회로만 렌더링하며, 선택 실패를 다른 회로로 대체하지 않는다. 일부 저장소를 한도·외부 오류로 검사하지 못하면 정상 후보 선택은 유지하되 Retry-After 경과 후(일반 외부 오류는 60초 후) 같은 검색의 후보·검증·선택 캐시를 비우고 재검사한다. 후보 선택으로 이 재검사 시점을 연장하지 않는다.

GitHub 라이선스 metadata의 deprecated GPL 식별자는 canonical SPDX 표기로 정규화한다. `NOASSERTION`은 일괄 허용하지 않으며, 고정 원문의 구조화된 CERN-OHL 고지와 README의 명시적인 전체 hardware 적용 범위가 일치하고 추가 제한이 없는 경우에만 선언된 라이선스와 원문 근거 URL을 반환한다. 제조사 공식 확인과 커뮤니티 라이선스 선언은 별개의 정보다. GitHub API의 정상 JSON 응답은 인증 설정별·URL별로 15분, 최대 128건·16MiB 범위에서 재사용한다.

상위 계층의 다른 시트를 검사하지 못해도 검색 부품을 포함한 하위 계층 자체가 완전하면 그 하위 원문을 별도 후보로 제공한다. 완전한 상위 계층을 제공할 수 있으면 포함된 하위 후보는 중복 노출하지 않는다. 선택된 하위 계층의 누락·순환 검사는 생략하지 않는다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `PROJECTS.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `catalog.py` | `catalog.json`의 안전한 ID·이름·저장소 내부 연결 경로를 검증하고 immutable catalog 제공(`load_catalog`, `catalog_by_id`) |
| `models.py` | 목록 메타데이터 `ProjectSummary`와 정규화 연결 정보를 포함한 상세 `Project` DTO |
| `netlist.py` | `normalize_netlist(bytes)`: KiCad export에서 연결 정보(parts/nets)만 제한된 메모리로 읽고 SHA-256과 함께 `NormalizedCircuit`으로 반환. 원본·경로·파일 핸들은 남기지 않음 |
| `repository.py` | `ProjectRepository`: `create_empty`, `create_demo`, `create_upload`, `import_netlist`(새 버전·대화 원자 생성), `list_owned`, `get_owned`(선택적 대화 버전), `rename_owned`, `delete_owned` |
| `visuals.py` | `load_demo_visuals()`가 데모 catalog의 회로도 출처 정본(HTTPS, commit, 원본·배포 hash, PNG 경로)을 검증. 누락·추가 ID나 손상 자산은 예외. 외부 다운로드 없음 |
| `external_circuit_search.py` | Exa 공개 웹 결과에서 회로도 이름과 파일을 확인하고 제조사·비공식 출처 후보를 정제. GitHub 저장소 후보 검색도 담당 |
| `external_schematic.py` | 공개 원본 후보를 검증·변환·메모리 캐시하고 서명 token으로 시트 조회. 같은 검색의 다른 후보 선택을 검증 |
| `schematic.py` | 별도 renderer의 KiCad CLI PDF export 경계와 Cloud Run ID token 전달 |
| `schematic_discovery.py` | GitHub tree에서 EDA 원본과 연결된 전체 회로도 자산 찾기 |
| `schematic_render.py` | 공개 PDF/SVG/PNG의 해시·회로도 페이지를 확인하고 제한된 크기와 해상도의 PNG로 렌더링 |
| `schematic_source.py` | 검증된 외부 회로도 source DTO와 서비스 오류 형식 |
