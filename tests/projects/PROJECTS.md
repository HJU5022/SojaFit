# projects

## 역할
- 넣는 것: 프로젝트 저장소의 입력 검증, 실제 PostgreSQL 소유권·원자성·cascade·스키마 권한 테스트.
- 넣지 않는 것: HTTP 계약(`tests/api/`), 업로드 파서·D5 평가.
- 담당: 서비스·운영

## 파일
- `PROJECTS.md` — 이 문서
- `test_project_repository.py` — 전 경계 소유자 필터, 관리자 접근 차단, 이름 변경, 생성 실패 롤백, 사용자·프로젝트 삭제 cascade, RLS·공개 역할 권한·FK 인덱스·CHECK

`uv run pytest -q tests/projects`. DB 테스트는 `TEST_AUTH_DATABASE_URL`로 지정한 격리 시험 DB에서만 실행한다. 각 시험은 임의 이름 schema에 인증 및 013 SQL을 적용하고 그 schema만 정리한다. URL이 없으면 DB 시험을 건너뛴다. 운영·공유 DB URL을 설정하지 않는다.
