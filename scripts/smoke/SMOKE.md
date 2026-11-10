# smoke

## 역할
- 이 폴더: 로컬 compose나 배포 주소의 API를 화면 대신 HTTP로 불러, 정상 사용자 흐름이 끝까지 이어지는지 단계마다 통과 · 실패로 남기는 점검 스크립트를 둡니다. 저장소 루트에서 실행합니다.
- 넣는 것: 서버 밖에서 HTTP로만 부르는 흐름 점검 스크립트.
- 넣지 않는 것: 원시 결과(`scripts/results/smoke/`), 서버 코드(`backend/`), 오프라인 회귀 시험(`tests/api/test_http_smoke.py`), 데모 LLM 응답 기록 · 재생 대조(`scripts/demo/`), 답 · 판정 채점(`evals/`).
- 담당: 서비스·운영

## 파일
- `SMOKE.md` — 이 문서
- `http_smoke.py` — 로그인 → 데모 회로 프로젝트 → 판정 질문(v3-01) · 조건 재개 → 승인(두 번째는 409) → 견적 → 다른 계정은 프로젝트 · run · 견적 · 승인 · 승인 사례를 404로만 봄을 HTTP로 한 번 돌려, 요청마다 상태 · `error.code` · `X-Request-ID` · ms와 SSE 이벤트 순서, `/openapi.json` 경로 · 연산 수, 이 작업 트리 커밋을 `scripts/results/smoke/smoke_<호스트>_<KST 날짜>_<시각>.json`에 남긴다. 질문 글은 `scripts/demo/record_demo.py`의 `QUESTIONS`를 읽는다

## 실행

```bash
# 1) 로컬 키 없는 compose(데모 버튼 A · B, 기록 응답 재생이라 LLM 호출 없음). --refusal은 9단계(v3-30 거절)를 더한다
uv run python scripts/smoke/http_smoke.py --base-url http://localhost:8000 --demo --refusal
# 2) 배포 주소(실제 계정 A · B, 4 · 5 · 9단계가 실제 LLM을 부른다). 비밀번호는 화면 · 셸 기록에 남지 않게 read -s로 넣는다
export SMOKE_A_EMAIL='<A 이메일>' SMOKE_B_EMAIL='<B 이메일>'
read -rs SMOKE_A_PASSWORD && export SMOKE_A_PASSWORD
read -rs SMOKE_B_PASSWORD && export SMOKE_B_PASSWORD
uv run python scripts/smoke/http_smoke.py --base-url https://<배포 주소>            # 어림 호출 수만 찍고 멈춤(종료 코드 2)
uv run python scripts/smoke/http_smoke.py --base-url https://<배포 주소> --confirm-live
```

종료 코드: 모두 통과 0, 통과 못 한 단계가 있으면 1, 요청 전에 멈추면 2.

## 단계

| 단계 | 계정 | 요청 | 통과 조건 |
|---|---|---|---|
| 1 | - | `GET /health`, `GET /openapi.json` | 200. 경로 · 연산 수를 결과에 남김 |
| 2 | A | `POST /api/auth/demo-login`(`--demo`) 또는 `POST /api/auth/login`, `GET /api/auth/me` | 200 |
| 3 | A | `GET /api/demo-circuits`, `POST /api/projects`, `GET /api/projects/{id}` | 200 · 201 · 200, v3-01 회로 이름이 목록에 있음 |
| 4 | A | `POST /api/projects/{id}/threads`, `POST /api/threads/{id}/runs`(v3-01) | 201, SSE 마지막이 `requires_input` |
| 5 | A | `POST /api/runs/{id}/resume`(물은 이름의 답 · 첫 역할 후보, `record_demo.py`와 같은 규칙) | SSE 마지막이 `completed` |
| 6 | A | `GET /api/runs/{id}`(message_id), `POST /api/messages/{id}/approvals` 두 번 | 200, 201, 두 번째는 409 `ALREADY_APPROVED` |
| 7 | A | `POST /api/approvals/{id}/quotes`, `GET /api/projects/{id}/quotes` | 201, 200이고 저장한 견적이 목록에 있음 |
| 8 | B | 로그인, A의 `GET /api/projects/{id}` · `/threads` · `GET /api/runs/{id}` · `GET /api/projects/{id}/quotes`, A의 메시지에 `POST /api/messages/{id}/approvals`, A의 승인에 `POST /api/approvals/{id}/quotes`, `GET /api/projects`, `GET /api/approved-cases`(A · B 각각) | 200, 404 `NOT_FOUND` 여섯(GET 넷 · POST 둘), B 목록에 A 프로젝트 · 승인 사례 없음(A 목록에는 A 사례가 있음) |
| 9 | A | (`--refusal`) 프로젝트 · thread, `POST /api/threads/{id}/runs`(v3-30) | SSE 마지막이 `refused` |

- 404는 "남의 자료는 없는 것처럼 숨긴다"는 설계라 8단계의 통과 조건이다(403이면 그 id가 있다는 것이 드러난다). 같은 id를 A는 200으로 읽는다(3 · 6 · 7단계).
- 8단계의 B가 보내는 POST 둘은 A가 이미 승인 · 견적을 만든 뒤에만 보낸다. 격리가 깨져도 DB 제약(메시지당 승인 1개 · 승인당 견적 1개)으로 새로 만들어지지 않고 409로 끝나 실패로 남는다. 승인 사례 삭제(DELETE)는 자료를 바꾸므로 보내지 않는다.
- 앞 단계 값(프로젝트 · thread · run · 승인 id)이 없으면 뒤 요청은 보내지 않고 `skip`으로 남는다. 8단계는 있는 값만으로 계속한다.
- [주의] `--base-url`은 서버의 `AUTH_ORIGIN`과 글자까지 같아야 한다(바꾸는 요청에 `Origin: <base-url>`을 붙이고 서버가 대조, 다르면 403 `ORIGIN_MISMATCH`). 로컬은 `http://localhost:8000`이고 `127.0.0.1`이면 다르다.
- [주의] 로그인은 계정마다 한 번만 보낸다. 같은 계정이 15분에 5번 틀리면 15분 잠긴다.
- [주의] `--demo`는 서버가 기록 응답을 재생한다(`DEMO_REPLAY=1`)고 보고 비용 확인을 하지 않는다. 키를 넣고 재생을 끈 서버에는 쓰지 않는다.
- [주의] 만든 점검용 프로젝트(`smoke v3-01 MM-DD HH:MM`) · 승인 · 견적은 지우지 않는다. 지우려면 화면이나 `DELETE /api/projects/{id}`로 지운다.
- 결과 파일에는 계정을 A · B로만 적고 비밀번호 · 쿠키 · 이메일 · 답 글 · 오류 문구를 넣지 않는다. 실패 원인 문구는 실행 화면에만 찍는다.
