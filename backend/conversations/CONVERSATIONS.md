# conversations

## 역할
- 이 폴더: 프로젝트 소유 대화·메시지·실행의 저장 경계와 내부 결과 형식을 둡니다.
- 넣는 것: 소유권 조건 SQL, 실행 상태 전이, 안전 결과 형식.
- 넣지 않는 것: HTTP 라우터, 그래프 실행, 가격·재고 응답.
- 담당: 서비스·운영

## 파일
- `CONVERSATIONS.md` — 이 문서
- `__init__.py` — 패키지 표시
- `dto.py` — 브라우저 결과 허용 목록
- `models.py` — 실행 상태와 저장 허용 결과 형식
- `repository.py` — 소유자 조건, 실행 생성·재개 및 결과 저장

`str(threads.id)`가 불변 LangGraph `thread_id` 정본이다. 프로젝트 삭제는 project 행 잠금으로 새 실행·재개와 직렬화하고 활성 실행이 있으면 거절한다. checkpoint 세 표와 project cascade는 같은 `DATABASE_URL`의 한 트랜잭션에서 정리되어 어느 단계가 실패해도 함께 rollback된다. 저장 결과는 answer, question_type, 품번, interrupt, 공개 판정·인용 메타데이터만 허용하며 request_id는 저장하지 않는다. 문서 질문의 raw chunk는 반환하지 않는다.
