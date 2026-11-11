# conversations

## 역할
- 이 폴더: 대화 저장소의 격리 PostgreSQL 시험과 공개 DTO 시험을 둡니다.
- 넣는 것: 소유권·제약·원자성·권한·삭제 잠금 검증.
- 넣지 않는 것: 운영 DB 접근, 실제 모델·검색 API 호출.
- 담당: 서비스·운영

## 파일
- `CONVERSATIONS.md` — 이 문서
- `test_dto.py` — 공개 및 저장 DTO 허용 목록, 그래프 상태의 공개 값 고르기(`public_state`), 참고(내 설정) 칸 고르기, 판정의 `preferred_mount`
- `test_profile.py` — 사용자 사실 기억: 칸 검사·틀 문장·version·지우기·의미 순위(InMemoryStore + 가짜 Voyage)·설정 API 422·403·401·503. DB 시험은 `TEST_THREAD_DATABASE_URL`, 색인 시험은 그 DB에 `vector` 확장이 있을 때만(색인 표가 `sojafit_agent`에 생기는지, 확장이 `extensions` 스키마에 있어도 준비·검색되는지)
- `test_repository.py` — 격리 DB에서 대화 저장소·스키마·삭제 잠금 시험
