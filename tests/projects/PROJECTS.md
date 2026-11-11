# projects

## 역할
- 넣는 것: 프로젝트 저장소의 입력 검증, 실제 PostgreSQL 소유권·원자성·cascade·스키마 권한과 제한된 KiCad 정규화 테스트.
- 넣지 않는 것: HTTP 계약(`tests/api/`), D5 평가.
- 담당: 서비스·운영

## 파일
- `test_external_circuit_search.py` — GitHub 저장소 URL 정제와 Exa 호출 상한
- `test_external_schematic.py` — 라이선스·원본·전체 시트·cache·서명 token 경계
- `test_schematic_discovery.py` — GitHub tree에서 완성 회로도 자산 판정
- `test_schematic_render.py` — PDF/SVG/PNG 렌더링과 출력 크기 제한
- `test_catalog.py` — 데모 15종의 단일 catalog, 연결 파일 존재, 중복 키와 안전하지 않은 ID 차단.
- `PROJECTS.md` — 이 문서
- `test_netlist.py` — 합성 입력의 크기·UTF-8·문법·깊이/token/부품/net 상한·정확한 불변 정규화와 hash
- `test_visuals.py` — 데모 15종 exact match·PNG hash, HTTPS·고정 경로·원본 hash 필수·추가 metadata 거절, 누락 자산·변조·잘못된 catalog 차단
- `test_project_repository.py` — 전 경계 소유자 필터, 관리자 접근 차단, 이름 변경, 생성 실패 롤백, 사용자·프로젝트 삭제 cascade, RLS·공개 역할 권한·FK 인덱스·CHECK, 업로드 정규화 전용 저장·rollback, 받은 회로 데모(c01 `attiny85_time_switch`)를 `received-20261030/c01`에서 읽어 저장

`uv run pytest -q tests/projects`. DB 테스트는 `TEST_AUTH_DATABASE_URL`로 지정한 격리 시험 DB에서만 실행한다. 각 시험은 임의 이름 schema에 인증 및 013 SQL을 적용하고 그 schema만 정리한다. URL이 없으면 DB 시험을 건너뛴다. 운영·공유 DB URL을 설정하지 않는다.
