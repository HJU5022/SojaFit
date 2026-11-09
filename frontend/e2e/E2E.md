# e2e

## 역할
- 넣는 것: 로컬 Vite 화면과 완전한 가짜 API를 사용하는 Playwright 사용자 흐름.
- 넣지 않는 것: 실제 모델·Mouser·공유 DB 호출, 운영 계정과 비밀값.

## 파일
- `E2E.md` — 이 문서
- `workbench.spec.ts` — 로그인 세션 복원부터 근거·판정 표시까지의 브라우저 smoke
- `full-flow.spec.ts` — 완료 판정·실시간 가격·사람 승인·가격 없는 견적·사례 삭제 전체 흐름
- `dummy-mode.spec.ts` — route 가로채기 없이 개발 전용 메모리 API로 직접 조작하는 전체 흐름
