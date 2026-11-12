# conversations

## 역할
- 이 폴더: 대화 저장소(`backend/conversations/`)의 공개 DTO 시험과 격리 PostgreSQL 시험.
- 넣는 것: 소유권·제약·원자성·권한·삭제 잠금 검증, 허용 목록 검증, 사용자 사실 기억 시험.
- 넣지 않는 것: 운영 DB 접근, 실제 모델·검색 API 호출.
- 담당: 서비스·운영

실행: `uv run pytest -q tests/conversations`(저장소 루트).

## 파일
| 파일 | 확인하는 것 |
|---|---|
| `CONVERSATIONS.md` | 이 문서 |
| `test_dto.py` | 공개·저장 DTO 허용 목록, 그래프 상태에서 공개 값 고르기(`public_state`), 참고(내 설정) 칸 고르기, 현재 응답의 `input_conditions` 허용 목록(비공개·잘못된 항목 제외), `SafeResult` 출력이 `runs.safe_result` CHECK의 필수 키를 항상 가지는지 |
| `test_profile.py` | 사용자 사실 기억: 칸 검사, 틀 문장, version, 지우기, 의미 순위(InMemoryStore + 가짜 Voyage), 설정 API의 422·403·401·503. DB 시험은 `TEST_THREAD_DATABASE_URL`, 색인 시험은 그 DB에 `vector` 확장이 있을 때만 |
| `test_repository.py` | 격리 DB에서 대화 저장소·스키마·삭제 잠금, 저장 메시지 페이지·소유권·읽기 전용 조회(조회 전후 행 수·run 시각 불변), 오래된 running의 recover(최근·활성 분석·타 사용자·추가 입력 대기·완료 결과는 보존), 표시 조건을 제외한 결과 저장 |
