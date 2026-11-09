# conversations

## 역할
- 이 폴더: 프로젝트 소유 대화·메시지·실행의 저장 경계와 내부 결과 형식을 둡니다.
- 넣는 것: 소유권 조건 SQL, 실행 상태 전이, 안전 결과 형식.
- 넣지 않는 것: HTTP 라우터, 그래프 실행, 가격·재고 응답.
- 담당: 서비스·운영

## 파일
- `CONVERSATIONS.md` — 이 문서
- `__init__.py` — 패키지 표시
- `memory_service.py` — 인증 사용자별 업로드·thread 소유권·DB 체크포인트·조건 재개·버전별 승인 기록, 질문·재개 때 사용자 사실 찾기(`profile_hints`). `THREADS_ENABLED=1`에서 사용하며 `--setup` CLI를 제공. `ensure_thread`가 React 대화와 같은 UUID의 분석 회로·thread를 처음 한 번 만들고 대상 부품을 고정한다(바꾸면 409, 넷리스트 원문 칸은 빈 글자)
- `profile.py` — 사용자 사실 3칸 장기 기억(SPEC 8.5): 칸 검사, 틀 문장, Store 덮어쓰기(version)·지우기, Voyage 의미 검색(키 없으면 순위 없이)
- `dto.py` — 브라우저 결과 허용 목록(참고(내 설정) `profile_hints` 포함), 그래프 상태에서 공개 값만 고르는 `public_state`
- `models.py` — 실행 상태와 저장 허용 결과 형식
- `repository.py` — 소유자 조건, 실행 생성·재개 및 결과 저장

`str(threads.id)`가 불변 LangGraph `thread_id` 정본이고, 같은 UUID가 사용자 분석 서비스(`sojafit_agent`)의 thread id다. 체크포인트·승인 기록·사용자 사실 기억(Store, namespace `(user_id, "profile")`)은 분석 서비스에만 있다. 승인 사례는 장기 기억이 아니라 승인 기록이다(11-09): 새 분석에 넘기지 않고 Store에 쓰지 않는다. 프로젝트 삭제는 project 행 잠금으로 새 실행·재개와 직렬화하고 활성 실행이 있으면 거절하며, public 행만 지운다. 같은 UUID의 분석 thread·checkpoint·승인 기록은 남는다(승인 기록은 `/api/memories`로 철회·삭제 표식). 저장 결과는 answer, question_type, 품번, interrupt, 공개 판정·인용 메타데이터만 허용하며 request_id는 저장하지 않는다. 문서 질문의 raw chunk는 반환하지 않는다.
