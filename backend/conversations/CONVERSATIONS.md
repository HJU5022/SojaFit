# conversations

## 역할
- 이 폴더: 프로젝트 소유 대화·메시지·실행의 저장 경계와 내부 결과 형식을 둡니다.
- 넣는 것: 소유권 조건 SQL, 실행 상태 전이, 안전 결과 형식.
- 넣지 않는 것: HTTP 라우터, 그래프 실행, 가격·재고 응답.
- 담당: 서비스·운영

## 파일
- `CONVERSATIONS.md` — 이 문서
- `__init__.py` — 패키지 표시
- `models.py` — 실행 상태와 저장 허용 결과 형식
- `repository.py` — 소유자 조건, 실행 생성·재개 및 결과 저장

`str(threads.id)`가 불변 LangGraph `thread_id` 정본이다. 프로젝트 cascade만으로 라이브러리 checkpoint는 삭제되지 않는다. Task 8은 소유권 검증·실행 중단과 `D5Service.delete_thread`를 프로젝트 삭제와 연결해야 하며 Task 13에서 cascade E2E를 검증한다. 라이브러리 API와 프로젝트 삭제는 현재 같은 트랜잭션이 아니므로 실패 복구와 동시 실행 경계가 미해결이다.
