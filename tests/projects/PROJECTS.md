# projects

## 역할
- 이 폴더: 프로젝트 저장소(`backend/projects/`)의 입력 검증, 실제 PostgreSQL 소유권·원자성·cascade·스키마 권한, 제한된 KiCad 정규화, 데모·외부 회로도 시험.
- 넣는 것: `backend/projects/`를 대상으로 한 `test_*.py`와 서비스 표 스키마 규칙 시험.
- 넣지 않는 것: HTTP 계약(`tests/api/`), 분석 실행 평가.
- 담당: 서비스·운영

실행: `uv run pytest -q tests/projects`. DB 시험은 `TEST_AUTH_DATABASE_URL`로 지정한 격리 시험 DB에서만 실행하고 각 시험은 임의 이름 schema에 SQL을 적용한 뒤 그 schema만 정리한다. URL이 없으면 건너뛴다. 운영·공유 DB URL을 설정하지 않는다.

## 파일
| 파일 | 확인하는 것 |
|---|---|
| `PROJECTS.md` | 이 문서 |
| `test_catalog.py` | 데모 단일 catalog, 연결 파일 존재, 중복 키와 안전하지 않은 ID 차단 |
| `test_visuals.py` | 데모 회로도 provenance(HTTPS, 고정 경로, 원본 hash)와 PNG hash, 추가 metadata 거절, 누락 자산·변조·잘못된 catalog 차단 |
| `test_netlist.py` | 합성 입력의 크기·UTF-8·문법·깊이/token/부품/net 상한, 불변 정규화와 hash, 원본 폐기 |
| `test_project_repository.py` | 격리 DB에서 전 경계 소유자 필터, 관리자 접근 차단, 이름 변경, 생성 실패 롤백, 사용자·프로젝트 삭제 cascade, RLS·공개 역할 권한·FK 인덱스·CHECK, 업로드 정규화 전용 저장, 받은 회로 데모 저장 |
| `test_service_schema.py` | 일회용 DB에서 서비스 표 규칙: 프로젝트·계정 삭제 연쇄(분석 대화·체크포인트), 체크포인트 삭제 트리거, 분석 대화 FK 거부, `runs.safe_result` 필수 키 CHECK, 승인 칸 NOT NULL·형식, 승인당 견적 중복 허용, 데모일 때만 `demo_id` |
| `test_external_circuit_search.py` | GitHub 저장소 URL 정제와 Exa 호출 상한 |
| `test_external_schematic.py` | 라이선스·원본·전체 시트·캐시·서명 token 경계 |
| `test_official_schematic.py` | 제조사 공식 원본 URL·등급·SHA-256 렌더 검증 |
| `test_schematic_discovery.py` | GitHub tree에서 완성 회로도 자산 판정, 네트워크 상한(격리된 HTTP 응답) |
| `test_schematic_render.py` | PDF/SVG/PNG 렌더링과 출력 크기 제한 |
