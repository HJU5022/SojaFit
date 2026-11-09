# projects

## 역할
- 넣는 것: 소유 사용자 조건이 포함된 프로젝트 SQL과 공개 DTO. 데모 5종의 정규화 연결 JSON을 복제한다.
- 넣지 않는 것: HTTP 라우트(`backend/api/`), 업로드 파서, 원본 넷리스트·가격 저장, D5 실행.
- 담당: 서비스·운영

## 파일
- `PROJECTS.md` — 이 문서
- `__init__.py` — 패키지 표시
- `models.py` — 목록 메타데이터와 정규화 연결 정보를 포함한 상세 DTO
- `repository.py` — `create_demo`, `list_owned`, `get_owned`, `rename_owned`, `delete_owned`. 모든 조회·변경·삭제에 `user_id` 조건 적용. 관리자 예외 없음

`auth.connection()`과 `db/013_projects.sql`을 사용한다. 생성은 프로젝트·회로를 한 트랜잭션으로 저장하고 삭제는 FK cascade를 사용한다. 데모 `source_sha256`은 기존 `connections.json` 바이트의 SHA-256이며 `parser_version`은 `demo-connections-v1`이다. 목록에는 연결 정보를 싣지 않고 상세·생성·이름 변경 결과에만 싣는다. 데이터 출처와 라이선스는 [CIRCUITS.md](../../data/circuits/CIRCUITS.md)를 따른다. 업로드 생성 인터페이스는 아직 없다.
