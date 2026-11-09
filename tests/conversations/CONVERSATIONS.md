# conversations

## 역할
- 이 폴더: 대화 저장소와 체크포인트의 격리 PostgreSQL 시험을 둡니다.
- 넣는 것: 소유권·제약·원자성·권한·체크포인트 검증.
- 넣지 않는 것: 운영 DB 접근, 실제 모델·검색 API 호출.
- 담당: 서비스·운영

## 파일
- `CONVERSATIONS.md` — 이 문서
- `test_dto.py` — 공개 및 저장 DTO 허용 목록
- `test_repository.py` — 격리 DB에서 대화 저장소·스키마·체크포인터 시험
