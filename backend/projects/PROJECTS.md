# projects

## 역할
- 이 폴더: 사용자 소유 프로젝트·정규화 회로 저장소와 공개 DTO, 데모 회로 catalog 검증, 외부 공개 회로도 검색·변환.
- 넣는 것: 소유 사용자 조건이 붙은 프로젝트 SQL(`repository.py`), 단일 catalog(`data/circuits/catalog.json`)의 데모 복제와 회로도 출처 검증, 제한된 KiCad export 정규화(`netlist.py`), 외부 회로도의 검색 후보 정제·원본 확인·PNG 변환.
- 넣지 않는 것: HTTP 라우트와 multipart 수신(`backend/api/`), 원본 넷리스트·가격 저장, 분석 실행(`backend/multi_agent/`).
- 담당: 서비스·운영

저장소는 `auth.connection()`과 `db/020_service_baseline.sql`의 표를 쓴다. 모든 조회·변경·삭제에 `user_id` 조건이 붙고 관리자 예외는 없다. 생성은 프로젝트와 회로를 한 트랜잭션으로 저장하고 삭제는 FK cascade를 쓴다. 업로드 정규화의 크기·깊이·개수 상한과 파서 버전은 `netlist.py` 상수(`MAX_BYTES`, `MAX_DEPTH`, `MAX_TOKENS`, `MAX_COMPONENTS`, `MAX_NETS`, `PARSER_VERSION`)가 정본이다. 데모 회로의 출처와 라이선스는 [CIRCUITS.md](../../data/circuits/CIRCUITS.md)를 따른다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `PROJECTS.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `catalog.py` | `catalog.json`의 안전한 ID·이름·저장소 내부 연결 경로를 검증하고 immutable catalog 제공(`load_catalog`, `catalog_by_id`) |
| `models.py` | 목록 메타데이터 `ProjectSummary`와 정규화 연결 정보를 포함한 상세 `Project` DTO |
| `netlist.py` | `normalize_netlist(bytes)`: KiCad export에서 연결 정보(parts/nets)만 제한된 메모리로 읽고 SHA-256과 함께 `NormalizedCircuit`으로 반환. 원본·경로·파일 핸들은 남기지 않음 |
| `repository.py` | `ProjectRepository`: `create_demo`, `create_upload`, `list_owned`, `get_owned`, `rename_owned`, `delete_owned` |
| `visuals.py` | `load_demo_visuals()`가 데모 catalog의 회로도 출처 정본(HTTPS, commit, 원본·배포 hash, PNG 경로)을 검증. 누락·추가 ID나 손상 자산은 예외. 외부 다운로드 없음 |
| `external_circuit_search.py` | Exa 공개 웹 결과에서 회로도 이름과 파일을 확인하고 제조사·비공식 출처 후보를 정제. GitHub 저장소 후보 검색도 담당 |
| `external_schematic.py` | 공개 원본 후보를 검증·변환·메모리 캐시하고 서명 token으로 시트 조회. 같은 검색의 다른 후보 선택을 검증 |
| `schematic.py` | KiCad CLI PDF export를 shell 없이 실행하는 경계 |
| `schematic_discovery.py` | GitHub tree에서 EDA 원본과 연결된 전체 회로도 자산 찾기 |
| `schematic_render.py` | 공개 PDF/SVG/PNG의 해시·회로도 페이지를 확인하고 제한된 크기와 해상도의 PNG로 렌더링 |
| `schematic_source.py` | 검증된 외부 회로도 source DTO와 서비스 오류 형식 |
