# STH 작업 기록

## 2026-11-04 조장 관리 SPEC 변경 분리
- 한 일: 미커밋 주요 문서 중 `SPEC.md`만 변경된 것을 확인하고, 인증·마스킹 반영 요청 초안을 저장소 밖에 보관한 뒤 `origin/main` 기준으로 되돌렸다. 당시 `origin/main`과 STH의 해당 파일 원본은 동일했다.
- 바꾼 파일: `SPEC.md`, `docs/worklog/sth.md`. 요청 초안은 저장소 밖 Codex 작업 폴더의 `sojafit-spec-auth-request.md`에 보관했다. 인증 코드와 다른 미커밋 변경은 유지했다.
- 확인: 저장 전 diff와 조장 관리 문서 규칙을 대조했다. 코드 테스트나 조장에게 요청 전달은 하지 않았다.
- 다음 할 일: 기존 계정 이메일 형식의 호환성을 확인하고, 정책이 확정되면 저장한 초안을 조장에게 전달해 `SPEC.md` 반영을 요청한다.

## 2026-11-04 원격 STH fast-forward 및 변경 확인
- 한 일: 기존 미커밋·미추적 변경을 `codex-sth-pull-safety-20261104` stash에 보관하고 `git pull --ff-only origin STH`로 `95ca940`에서 `013e5a1`로 갱신했다. `git stash apply --index`는 `SPEC.md`와 이 작업 기록을 자동 병합했고 미해결 충돌은 없었다. 안전 사본 stash는 유지했다.
- 받은 내용: MCP `search_corpus` 응답 검증·stdio 세션 재사용 검색기와 그래프 주입 경로, 검색 장애를 빈 결과와 구분하는 분기·턴 초기화, NumPy 선행 import, 관련 테스트·문서 및 main의 변경이다. MCP 검색기는 인자로 주입할 때 사용하며 기본 검색 경로를 자동 전환하지 않는다.
- 보존 확인: 인증 코드·테스트·시드·작업서와 미추적 측정 JSON을 stash와 줄바꿈 정규화 후 해시 비교해 일치했다. `SPEC.md`와 작업 기록의 양쪽 변경은 자동 병합 상태로 보존했다. 주요 문서 `SPEC.md`의 기존 미커밋 인증 변경은 조장 검토 대상이다.
- 검사: 샌드박스 집중 테스트는 진행 중 실패 표시 후 완료 전 중단했다. 같은 범위를 로컬 권한에서 `.venv/Scripts/python.exe -m pytest -q tests/graph tests/mcp_skill tests/repo tests/api -p no:cacheprovider --maxfail=1`로 재실행해 130 passed, 16 skipped (10.38초). 첫 실행은 최종 실패 상세를 수집하지 못해 원인을 확정하지 않는다. `git diff --check` 통과, 미해결 충돌 파일 없음.
- 미검증: 건너뛴 DB 의존 경로, 실제 Cloud Run, 전체 평가셋 재측정. 풀은 푸시·배포·공유 DB 변경을 포함하지 않았다.
- 다음 할 일: 인증 변경에 대한 조장 문서 반영을 요청하고, 실제 격리 DB 기반 MCP 경로와 배포 검증은 선행 환경이 준비되면 별도 실행한다.

## 2026-11-04 STH 충돌 상태 점검
- 한 일: 현재 STH와 원격 STH·main의 충돌 가능성 및 미커밋 변경 겹침을 확인했다. Git 병합·브랜치 이동·커밋·푸시는 하지 않았다.
- 확인 결과: 로컬 STH `95ca940`은 원격 STH `013e5a1`보다 21커밋 뒤이며 fast-forward 가능 상태다. `git ls-remote --heads origin main STH`에서 원격 main `4dc4685`, STH `013e5a1`이 로컬 원격 추적 참조와 일치했다. `git status`, `git diff --name-only --diff-filter=U`상 진행 중인 병합이나 미해결 파일은 없다.
- 병합 예행 확인: 별도 임시 Git object 디렉터리를 사용해 `git merge-tree --write-tree origin/STH origin/main`을 실행한 결과 충돌 없이 종료 코드 0이었다. 이는 해당 시점 커밋 간 확인이며 이후 원격 변경은 포함하지 않는다.
- 미커밋 변경: 원격 STH 변경과 겹치는 `SPEC.md`, `docs/worklog/sth.md`를 임시 파일에서 3방향 비교했다. 원본 줄바꿈 그대로는 각 1곳 충돌이었으나 CRLF/LF를 LF로 통일한 비교에서는 두 파일 모두 충돌 0이었다. 실제 Git 병합 결과를 보장하는 검증은 아니며 기존 변경을 보존한 채 통합 시 재확인해야 한다. `SPEC.md`의 인증 문구는 조장 소유 주요 문서에 해당하므로 팀 규칙에 따라 조장에게 반영을 요청한다.
- 바꾼 파일: `docs/worklog/sth.md`. 기존 미커밋 변경과 미추적 측정 결과는 유지했다. 코드 테스트는 실행하지 않았다.
- 다음 할 일: 미커밋 변경을 안전하게 보존하고 원격 참조를 다시 확인한 뒤 STH를 통합한다. 작업 기록은 양쪽 내용을 모두 보존하고, 줄바꿈과 주요 문서 수정 권한을 확인한다.

## 2026-11-04 로그인 화면·배포 계정 검토
- 한 일: 현재 작업 트리의 화면 설계, 인증·관리자 API, 데모 계정 시드와 배포 검증 기록을 대조했다.
- 화면: `backend/web/`에는 설계 문서만 있고 로그인·관리자 UI는 없다. 과거 수동 화면은 제거됐으며 `tests/api/test_health.py`는 루트 404를 기대한다. 로그인·사용자 확인·로그아웃과 관리자 목록·일반 계정 활성 상태 변경 API는 있으나 실제 브라우저 연결은 미검증이다. FastAPI 직접 제공 여부와 상호작용은 미결이므로 서비스 담당과 정하고 작업 범위·수용 기준을 확정한 뒤 화면과 기존 테스트를 함께 고친다. 사용자 화면 표시만으로 관리자 권한을 보장하지 말고 서버 측 검사를 유지한다.
- 배포 비밀값·평가 계정: 비데모 서버는 32바이트 이상 `AUTH_SECRET`을 요구하며 `AUTH_ORIGIN`은 출처 검사와 Secure 쿠키에 영향을 준다. CLI 계정 생성과 로컬 Compose 데모 시드는 있으나 실제 Cloud Run 비밀값·DB·평가 계정 설정 여부는 확인되지 않았다. 공개 데모 계정은 실제 평가 계정으로 쓰지 않는다. 배포 담당자와 접근 권한·대상 DB 및 스키마 이력·비밀값 주입 방식·별도 평가 계정 전달 방법을 확인하고 격리 환경부터 검증한다. 키 변경 시 기존 세션은 재로그인이 필요하다.
- 확인: `backend/web/WEB.md`, `backend/web/design.md`, `SPEC.md`, `docs/specs/login-auth.md`, `backend/main.py`, `backend/auth.py`, `tests/api/test_health.py`, `docker-compose.yml`, `.env.example`, `docs/GATES.md`와 기존 로컬 실측 기록을 대조했다. `git status --short --branch`상 STH는 저장된 `origin/STH`보다 21커밋 뒤에 있어 구현 전 최신 상태를 확인해야 한다. 원격을 새로 조회하지는 않았다.
- 바꾼 파일: `docs/worklog/sth.md`. 코드 테스트·실제 배포 접근·비밀값 확인 또는 계정 생성은 하지 않았다.
- 다음 할 일: 화면 담당과 제공 방식·관리자 메뉴 범위 및 수용 기준을 합의하고, 배포 담당과 앞 절의 Cloud Run 재개 조건을 확인한다. 기존 미커밋 변경을 보존한 채 최신 브랜치 차이를 검토한다.

## 2026-11-04 인증 후속 검증
- 목적·조건: 격리 PostgreSQL과 Windows 단일 프로세스에서 로그인 1건과 실제 scrypt 2건 동시 실행을 비교하고, 두 슬롯이 찬 동안 세 번째 요청의 503과 메모리를 확인한다. 외부 모델 호출과 비용은 없다.
- 명령: `TEST_AUTH_DATABASE_URL`을 로컬 테스트 전용 DB로 지정하고 `.venv/Scripts/python.exe scripts/auth/measure_scrypt_concurrent.py` 실행. `uv` 실행 파일을 찾지 못해 기존 가상환경을 직접 사용한다.
- 중단 조건: 테스트 DB 연결 불가, 동일 날짜 결과 파일 존재, 검증 실패 또는 과도한 자원 사용 시 중단한다. 기존 결과는 덮어쓰지 않는다.
- 결과: 로컬 PostgreSQL 16.15 임시 컨테이너에 인증 SQL 003·005·006을 적용하고 `.venv/Scripts/python.exe -m pytest -q tests/api -p no:cacheprovider` 실행: 36 passed (20.44초). 임시 컨테이너는 종료·자동 제거했다.
- 실제 scrypt 측정: 두 로그인 200, 겹침 456.91ms, 두 검증 중 세 번째 503, 단일·두 건 최대 working set 184.30·312.73MiB. 결과 `scripts/results/auth/scrypt_concurrent_2026-11-04.json`. Windows 단일 Python 프로세스에서 각 조건 한 번 측정한 값이며 DB·Cloud Run 메모리와 일반 요청 지연을 뜻하지 않는다.
- 배포 확인: 공개 health 주소는 이 실행 환경의 DNS 조회에 실패했고, 서비스 URL의 프로젝트 번호에 대한 `gcloud projects describe`는 현재 계정 권한 부족으로 실패했다. 배포·공유 DB는 변경하지 않았다.
- 업무 데이터: 실제 업무 API·DB Store·승인 흐름이 없어 소유권 검사를 연결할 대상이 없음을 `backend/main.py`, `backend/graph/GRAPH.md`, `db/manual/MANUAL.md`에서 확인했다. 팀의 연동 경계 합의와 업무 기능 구현 후 교차 접근을 시험해야 한다.
- 바꾼 파일: 이 작업 기록과 위 측정 결과 JSON. 평가셋 재측정, Cloud Run 인증·설정 및 실제 업무 데이터 소유권은 확인하지 못했다.
- 다음 할 일: 배포 담당자에게 해당 프로젝트의 읽기 권한 또는 리비전·메모리·포트·DB 설정 확인을 요청하고, 업무 API 담당과 소유권 연동 경계를 확정한다.

### 접근 문제로 보류 — Cloud Run 검증 재개 방법
- 중단 지점: 2026-11-04 서비스 주소에 표시된 프로젝트 번호 `559369539072`의 프로젝트 조회가 현재 인증 계정의 권한 부족으로 실패했다. 공개 `/health` 요청은 이 실행 환경의 DNS 조회 실패로 응답을 받지 못했다. DNS 실패만으로 서비스 장애라고 판단하지 않는다.
- 재개 조건: 배포 담당자에게 실제 프로젝트 ID·서비스명·리전 확인과 Cloud Run 설정 및 필요 로그의 읽기 권한을 요청한다. 권한을 받을 수 없으면 담당자가 리비전, 포트, 메모리, 인스턴스·동시 요청 설정과 DB 스키마 적용 여부를 확인해 전달한다. 별도로 테스트용 계정과 격리 검증 환경을 준비한다. 비밀번호, 토큰, DB 주소 등 비밀값은 작업 기록이나 채팅에 적지 않는다.
- 재개 순서: ① 접근 가능한 환경에서 `/health`와 실제 배포 리비전을 확인한다. ② 포트 8000과 서비스 설정, 대상 DB 및 인증 스키마 적용 이력을 읽기 전용으로 대조한다. ③ 테스트 계정으로 HTTPS 쿠키·Origin, 로그인·`/api/auth/me`·로그아웃 및 세션 거부를 검증한다. ④ 격리 환경에서 DB 장애 및 두 슬롯 점유 시 503을 확인하고, 여러 인스턴스의 메모리·오류·지연은 시험 조건과 예산을 정한 뒤 측정한다. 실제 관측과 미검증 항목을 이 기록에 추가한다.
- 안전 경계: 공유·운영 DB 변경, 배포, 부하 시험 및 실제 계정 사용은 대상과 팀 절차를 확인한 후 진행한다. 로컬 36건 통과와 scrypt 측정 결과는 Cloud Run 검증을 대신하지 않는다.
- 별도 선행 조건: 업무 데이터 소유권 검사는 권한 문제와 별개로 업무 API·DB Store·승인 흐름과 소유권 경계 합의가 필요하다. 구현이 준비되면 위 업무 데이터 항목의 A/B 교차 접근 시험부터 진행한다.

## 2026-11-03 인증 후속 작업 준비
- 한 일: 업무 데이터 소유권, Cloud Run 인증 검증, scrypt 동시 처리 제한의 현재 구현과 선행 조건을 문서·코드에서 대조했다. 아래는 작업 제안이며 팀 합의나 실행 결과가 아니다.
- 업무 데이터 소유권: `docs/specs/login-auth.md`의 후속 연동 계약을 기준으로 서비스·에이전트 담당이 thread 소유권 확인 위치, Store namespace와 사용자 ID 변환 경계, 견적 승인 권한을 합의한다. 업무 API·승인 흐름·DB Store와 업무 표 적용이 준비되면 세션의 사용자 ID로 각 리소스 조회·변경을 제한하고 A/B 교차 접근 및 재접속·재시작 후 격리를 시험한다. `backend/graph/memory.py`는 namespace 규칙만 제공한다.
- Cloud Run: 배포 담당과 서비스·리비전, 대상 DB와 스키마 적용 이력, 접근 권한, 테스트 계정, 비용·시험 시간을 확인한다. 격리 환경에서 먼저 `/health`, HTTPS 쿠키·Origin, 로그인·세션·로그아웃, DB 장애와 2개 슬롯 점유 시 503, 로그의 민감값 노출 여부를 확인한다. 운영 DB 변경이나 배포는 팀 절차에 따라 별도 진행한다. `Dockerfile`은 8000번 포트로 고정되어 있어 실제 서비스의 포트 설정을 대조한다.
- 동시 처리: 현재 동일 PostgreSQL DB의 트랜잭션 advisory lock 두 칸이 로그인 경로를 제한하며 초과 요청은 503이다. 기존 격리 DB 테스트와 Windows 로컬 실측을 기준으로 재현하고 Cloud Run의 인스턴스·메모리·여러 프로세스 조건에서 별도 확인한다. 연결이 검증 도중 끊어지면 잠금이 먼저 해제될 수 있고 계정 생성 CLI는 제한 범위 밖이다. 2건을 변경할지, 초과 요청 재시도 방식과 목표 처리량은 측정 후 결정한다.
- 바꾼 파일: `docs/worklog/sth.md`.
- 확인 방법: `git status --short --branch`, 관련 폴더 설명·`docs/specs/login-auth.md`·인증 코드·테스트·배포 설정·기존 로컬 실측 기록을 대조했다. 새 테스트나 외부 환경 접근은 수행하지 않았다.
- 확인 못 한 것: 현 Cloud Run 리비전·설정과 인증 동작, 공유 DB 스키마·권한, 실제 업무 리소스의 교차 사용자 접근, 배포 환경 부하·메모리.
- 다음 할 일: 담당자와 연동 경계 및 격리 검증 환경을 확정하고, 인증 DB 테스트를 실행한 뒤 배포 검증과 업무 기능 연동을 각각 진행한다.

## 2026-11-03 로그인 이메일 입력·응답 보완
- 한 일: 로그인 API·계정 생성 CLI에 같은 이메일 형식 및 100자 제한을 적용했다. 데모 시드에도 동일 길이 제한을 더하고, 잘못된 기존 주소는 관리자 응답에서 전부 가려 목록 조회가 실패하지 않게 했다.
- 바꾼 파일: backend/auth.py, backend/main.py, db/007_demo_accounts.sql, tests/api/test_auth.py, docs/specs/login-auth.md, SPEC.md, docs/worklog/sth.md.
- 실행한 명령과 결과: `uv run --no-sync python -m pytest tests/api/test_auth.py -q -p no:cacheprovider` — 18 passed, 14 skipped (격리 인증 DB 미설정). `git diff --check` 통과.
- 확인 못 한 것: DB 통합 테스트는 건너뛰었고 Cloud Run·프록시 로그 및 운영 DB 설정은 접근할 수 없어 확인하지 않았다.
- 다음 할 일: TEST_AUTH_DATABASE_URL이 있는 환경에서 데모 시드 및 인증 DB 테스트를 실행한다.

## 2026-11-03 새 main 구조 병합과 MCP 자료 보관
- 한 일: `f271553`을 STH에 병합하고 MCP 테스트·측정 스크립트 및 원시 자료 15개는 요청에 따라 저장소 밖에 보관했다. stash의 수정된 MCP 테스트 사본도 별도로 보관했다.
- 정리: MCP 조사 문서의 외부 보관 자료와 사전등록 경로를 반영했다. 로그인 마스킹 변경은 이 MCP 커밋에서 제외했다.
- 확인: 충돌 없음, 외부 보관 사본 해시 대조, stage 변경의 `git diff --cached --check`, MCP 조사 문서 상대 링크 0건 누락. 테스트는 `uv` 실행 파일을 찾지 못해 실행하지 못했다.
- 다음 할 일: 팀과 MCP 테스트·측정 자료 위치를 정하고 복원한 뒤 구조 검사와 MCP 회귀 테스트를 실행한다. 원시 자료가 저장소 밖에 있어 현재 클론만으로 실측을 재현할 수 없다.

## 2026-11-03 최신 main 통합 및 MCP 문서 재분류
- 한 일: 최신 main `5760105`를 STH에 병합하고 자동 충돌을 수동 해결했다. 이전 `docs/mcp/`의 MCP 조사·실측·미합의 제안 문서 10개를 기존 `docs/research/`로 옮기고 폴더를 제거했다. 검색 도구 작업서는 `docs/specs/mcp-search-tools.md`에 유지했다.
- 코드 병합: STH 관리자 계정 API의 이메일 사용자명 마스킹과 해당 테스트를 보존했다. 구 `docs/README.md`·`docs/specs/README.md`·`backend/mcp_skill/README.md`·`scripts/README.md`는 main의 새 설명 파일로 대체했다.
- 문서 정합: `docs/research/RESEARCH.md`, `docs/specs/SPECS.md`와 `SOJAFIT.md` 신규 파일 항목을 맞췄다. 이동 문서의 현재 링크는 새 이름·경로로 바꿨다. `SPEC.md`의 stash 변경은 조장 소유 문서 규칙에 따라 작업 트리에서 제외하고 원본 stash에 남겼다.
- 확인: 충돌 미해결 파일 0, `git diff --check` 통과, 오래된 현재 경로 참조 0. 앱·회귀 테스트는 실행하지 않았다. 기존 stash는 안전을 위해 유지했다.
- 상태: STH가 로컬 merge commit을 포함해 `origin/STH`보다 23커밋 앞서며 push하지 않았다.
- 다음 할 일: 팀 리드가 소유한 `SOJAFIT.md`의 기존 MCP 서버 설명이 main 기준 자리표시자로 남아 있다. STH MCP 변경 PR에서 해당 설명 갱신을 리드에게 요청한다.

## 2026-11-03 나머지 MCP 도구 연결 위치 점검
- 한 일: 문서 조회·TSC 웹 후보·PDF 무결성·회로 정보 도구의 현재 코드 호출처와 그래프에서의 후보 사용 상황을 대조했다.
- 결론 제안: 질문 응답 그래프는 우선 `search_corpus`만 연결한다. 문서 메타데이터는 근거가 있을 때 선택 호출, 웹 검색·PDF 검증·회로 정보는 별도 정책과 사용 근거가 정해질 때까지 그래프 기본 경로에 넣지 않는다.
- 바꾼 파일: `docs/mcp/mcp-tool-contract-review.md`, `docs/worklog/STH.md`.
- 확인 못 한 것: 팀의 도구 노출 결정, 코퍼스 밖 공개 품번 정책, 사용자 회로 접근 요구. 코드·테스트는 수정하거나 실행하지 않았다.

## 2026-11-03 search_corpus 연결 계약 확인
- 한 일: 현재 STH MCP 도구와 원격 main `e25558a` 그래프의 입력·청크 필드·빈 결과 분기를 대조했다.
- 검증: 가짜 검색기를 넣은 별도 MCP stdio 프로세스에서 정상 청크 1건·빈 목록·합성 예외를 각 1회 호출했다. 성공은 `structuredContent.result`, 빈 결과는 빈 텍스트 블록 목록, 오류는 `isError=true`와 예외 문구를 포함하는 텍스트로 관찰됐다. DB·외부 API·실제 키는 사용하지 않았다.
- 바꾼 파일: `docs/mcp/mcp-tool-contract-review.md`, `docs/worklog/STH.md`.
- 확인 못 한 것: 실제 DB 오류의 응답·민감정보 노출 여부, 여러 청크·다른 SDK 버전, LangGraph와 MCP의 실제 통합. 다음 할 일: 오류 비노출 및 실패 구분 계약을 담당자와 협의한다.

## 2026-11-03 MCP 도구 계약 점검 문서 분리
- 한 일: 기존 구현 계획에 적은 도구별 계약·사용처 점검을 별도 문서로 분리하고 문서 목록과 구현 계획에 연결했다.
- 바꾼 파일: `docs/mcp/mcp-tool-contract-review.md`, `docs/mcp/mcp-tool-implementation-plan.md`, `docs/mcp/README.md`, `docs/worklog/STH.md`.
- 확인: 관련 문서의 로컬 링크 21개 중 누락 0개, `git diff --check` 통과. 애플리케이션 테스트와 외부 호출은 새로 수행하지 않았다.

## 2026-11-03 MCP 도구 계약 1차 점검
- 한 일: 다섯 도구의 입력·출력·실행 조건·한계와 사용처 제안을 정리하고 `search_corpus`의 품번 목록 및 빈 결과·장애 처리 협의안을 작성했다.
- 바꾼 파일: `docs/mcp/mcp-tool-implementation-plan.md`, `docs/worklog/STH.md`. 기존 로그인·MCP 코드 변경은 보존했다.
- 실행한 명령과 결과: `uv run --no-sync pytest -q -rs tests/test_mcp_search.py tests/test_mcp_manifest.py -p no:cacheprovider` — 36 passed.
- 확인 못 한 것: 실제 코퍼스 DB·Exa·LangGraph 전체 연동, 팀의 도구 노출·입력 상한 결정. 다음 할 일: 그래프·검색 담당자와 계약 대조 및 팀 디렉터리 정리 후 경로 재확인.

## 2026-11-03 MCP 두 사람 작업 분담 문서 분리
- 한 일: 두 사람의 작업 순서·의존 관계·완료 기준을 별도 문서로 옮기고 인수인계 문서와 문서 목록에서 연결했다.
- 바꾼 파일: `docs/mcp/mcp-two-person-work-plan.md`, `docs/mcp/mcp-collaboration-handoff.md`, `docs/mcp/README.md`, `docs/worklog/STH.md`.
- 확인: 관련 문서의 로컬 링크 17개 중 누락 0개, `git diff --check` 통과. 애플리케이션 테스트·외부 호출은 하지 않았다.

## 2026-11-03 MCP 공동작업 인수인계
- 한 일: MCP 도구의 구현·사용처·정보 경계·LangGraph 연결 검토·검증 한계와 팀 결정 사항을 인수인계 문서로 정리하고 두 사람의 작업 분담·의존 관계·완료 기준을 제안했다.
- 바꾼 파일: `docs/mcp/mcp-collaboration-handoff.md`, `docs/mcp/README.md`, `docs/worklog/STH.md`.
- 확인: 인수인계 문서와 목록의 로컬 링크 14개 중 누락 0개, `git diff --check` 통과. 애플리케이션 실행이나 외부 API 호출은 하지 않았다.

## 2026-11-03 MCP 도구 사용처와 문서 디렉터리 정리
- 한 일: 다섯 도구의 실제 호출처와 제안 사용처, 미결 사항을 구현 계획에 기록하고 관련 문서 7개를 `docs/mcp/`로 모았다. 기존 그래프 연결과 도구 삭제는 수행하지 않았다.
- 바꾼 파일: `docs/mcp/`, `docs/README.md`, `SOJAFIT.md`, `evals/PREREGISTER.md`, `docs/worklog/STH.md`.
- 확인: 이동 문서·목록의 상대 링크 91개를 확인해 누락 0개. `git diff --check` 통과. 이전 작업 기록의 옛 경로는 당시 기록으로 보존하며 현재 문서는 `docs/mcp/`에 있다. 실제 DB·외부 API·LangGraph 연결은 실행하지 않았다.

### 2026-11-03 MCP 입력 경계 및 구현 계획 정합성

- `search_tsc_web`의 문서 ID 길이를 `get_corpus_document`와 동일한 1~200자로 검증해 내부 예외 대신 경계에서 입력 오류를 반환하도록 맞췄다. 빈 값·200자·201자 조건의 회귀 테스트를 추가했다.
- 구현 계획의 MCP 도구 수를 5개로 고치고, 로컬 PDF 무결성 및 공개 회로 조회는 구현됐으며 PDF 다운로드·내용 검증과 사용자 회로 권한은 미구현임을 구분했다.
- 검증: 프로젝트 루트에서 `uv run --no-sync pytest -q -rs tests/test_mcp_search.py tests/test_mcp_manifest.py tests/test_graph_read_input.py tests/test_rag_retrieve.py tests/test_graph_search.py` — 57 passed, 1 skipped (`TEST_DATABASE_URL` 미설정). `git diff --check` 통과.

## 2026-11-03 로그인 정보 응답 마스킹
- 한 일: 로그인 입력 검증 오류에서 입력값을 응답하지 않도록 하고 관리자 계정 목록 이메일을 `a***@domain` 형식으로 마스킹했다. 로그인 작업서와 SPEC에 기준을 추가했다.
- 바꾼 파일: backend/main.py, tests/test_auth.py, docs/specs/login-auth.md, SPEC.md, docs/worklog/STH.md.
- 실행한 명령과 결과: `uv run --no-sync python -m pytest tests/test_auth.py -q -p no:cacheprovider` — 11 passed, 14 skipped (격리 인증 DB 미설정). `git diff --check` 통과.
- 확인 못 한 것: 격리 DB 통합 시험과 배포 환경의 실제 프록시·서버 로그.
- 다음 할 일: 격리 DB가 준비되면 건너뛴 인증 통합 테스트를 실행한다.

### 2026-11-03 우선순위 2 MCP 도구 기본 기능

- `verify_tsc_pdf`를 저장소 TSC 표본 3건의 서명·바이트 크기·SHA-256 무결성 대조로 구현했다. 내용 파싱 검증과 신규 PDF 다운로드는 하지 않고 미검증 상태를 반환한다.
- `get_circuit_info`를 고정 공개 회로 카탈로그와 기존 `circuit_around` 함수에 연결했다. 임의 파일 경로를 받지 않는다.
- MCP/spec/폴더 안내/구현 계획을 갱신하고 PDF 표본·회로 조회·잘못된 입력 및 stdio 호출 시험을 추가했다. 첫 실행은 manifest 문서 정보에 bytes가 없어 4건 실패했고, bytes 필드를 포함한 뒤 재실행해 `tests/test_mcp_search.py tests/test_mcp_manifest.py tests/test_graph_read_input.py tests/test_rag_collect.py tests/test_rag_parse.py` 44 passed.

## 2026-11-03 MCP·웹 검색 후보 논의 초안
- 사용자 확인: W02~W08 7질의, 공급자당 최대 7회·재시도/본문 추출 없음·15초 제한·총 지출 $0, 공식 도메인 적중 4~7/7과 중앙값 0.5~5초의 사전 기대를 초안에 기록했다. 최신 원격 main SPEC과 11-03 공식 가격을 읽기 전용으로 대조했다. 비교 API 호출과 실험 사전등록은 하지 않았다.
- 무료 기능 탐색: Exa 익명 MCP 초기화·도구 목록 HTTP 200, 공개 W01 검색 1회 HTTP 200·1,172.74ms. 응답에 manifest와 경로가 일치하는 공식 도메인 PDF 링크가 있었으나 원본 PDF·개정·해시는 확인하지 않았다. 공급자 비교 및 운영 성능 결과가 아니다. 초기 도구 형식 출력의 Windows cp949 오류는 ASCII 출력으로 재조회해 해결했다.
- 추가 준비: manifest의 8개 문서 제목·개정·ID를 대조해 웹 검색 질문, 품번·출처·개정 구분, 24회 상한 비용 추정과 무료 Exa 연결 탐색 조건을 초안에 추가했다. 공식 정답·품질 결과는 아니다.
- 한 일: 2026-11-02 조사 내용을 바탕으로 프로젝트 도구별 외부 MCP 후보와 웹 검색 비용·적합성, 미결 사항 및 다음 논의·검증 절차를 초안으로 정리했다.
- 바꾼 파일: docs/mcp-tool-candidates-draft.md, docs/DOCS.md, docs/worklog/STH.md.
- 확인: 프로젝트 MCP 안내·SPEC·문서 목록과 초안의 경로를 대조한다. 외부 가격은 2026-11-02 공식 안내 기준이며 도입 전 재확인한다.
- 확인 못 한 것: Tavily·Brave 실제 호출, 공급자 간 품질·지연·비용 비교, Exa 링크의 PDF 원문과 키 없는 데모의 실시간 웹 검색 평가 인정 여부.

## 2026-11-02 최신 main 반영 및 인증 변경 검증
- 한 일: 원격 main 404f2e1을 로컬 main과 STH에 fast-forward로 반영하고 보관한 로그인·데모 시드·인증 키 변경을 복원했다. .env.example, README, backend/main.py, db/DB.md, tests/TESTS.md의 충돌에서 양쪽 유효 내용을 보존했다.
- 확인: 격리 PostgreSQL에서 PYTHONUTF8=1로 전체 pytest를 실행해 75건 통과·10건 건너뜀. 최초 실행은 동결 데이터의 Windows CRLF 체크아웃 때문에 해시 검사 1건이 실패했다. 정규화한 값과 Git 원본이 기록된 해시와 일치함을 확인한 뒤 작업 사본을 동일한 Git 원본 바이트로 복원하고 재실행했다. 동결 데이터는 커밋에 포함하지 않는다.
- 확인 못 한 것: 클라우드 비밀값과 배포, 운영자 메뉴 UI, RAG DB가 필요한 검사 10건.

## 2026-11-02 로그인 피드백과 인증 키 실측
- 한 일: 격리된 Compose PostgreSQL에서 데모 시드와 비데모 기본 계정 차단을 확인하고 로컬 AUTH_SECRET으로 역할별 로그인·관리 API·세션 HMAC·키 교체·로그아웃을 각 3회씩 확인했다. 키와 토큰은 기록하지 않았다.
- 바꾼 파일: docs/auth-feedback-key-verification.md, docs/DOCS.md, docs/worklog/STH.md.
- 확인: TestClient 실측 6회 성공, 전체 pytest 75건 통과·RAG 관련 10건 건너뜀. 실행 환경과 개별 시간은 실측 문서에 기록했다.
- 확인 못 한 것: 운영자 메뉴 UI, 실제 API 컨테이너의 .env 전달 및 클라우드 배포, 동시 부하.

## 2026-11-02 인증 키와 세션 저장값 연결
- 한 일: 세션 토큰은 난수로 유지하고 AUTH_SECRET이 있으면 HMAC-SHA256으로 DB 저장값을 계산하도록 변경했다. 키 없는 데모는 기존 SHA-256을 유지하며 데모 외 환경은 32바이트 이상 키를 요구한다. 로컬 .env에 비어 있던 키를 생성하고 값은 기록하지 않았다.
- 바꾼 파일: backend/auth.py, backend/main.py, tests/test_auth.py, tests/TESTS.md, docs/auth_boundary_after_merge.py, .env.example, README.md, SPEC.md, docs/specs/login-auth.md.
- 확인: 키 설정·미설정, 앱 시작, 키 변경과 세션 거부, 로그인·로그아웃을 격리 PostgreSQL에서 검사했다. 전체 pytest 75건 통과, RAG DB 관련 10건 건너뜀. 후속 키 관련 재검사 4건 통과.
- 확인 못 한 것: 클라우드 비밀값 설정과 배포 반영. 키 전환 전 세션은 재로그인이 필요하다.

## 2026-11-02 데모 시드 검증과 모드 제한
- 한 일: DB 문서의 시드 설명을 갱신하고 실제 시드 SQL의 기본값·사용자 지정·일부 설정·데모 모드별 동작을 격리 DB 회귀 테스트에 추가했다. 공개 기본 계정은 DEMO_MODE=1에서만 생성하도록 제한하고 명시적으로 지정한 네 값은 계속 허용한다.
- 바꾼 파일: db/DB.md, db/007_demo_accounts.sql, docker-compose.yml, tests/test_auth.py, tests/TESTS.md, .env.example, README.md, SPEC.md, docs/specs/login-auth.md.
- 확인: 모드 제한 전 새 테스트 1건이 실패했고 제한 후 5건 모두 통과했다. 격리 Compose 새 볼륨에서 DEMO_MODE=1은 계정 2개, 0은 0개를 확인했다. UTF-8 모드의 전체 pytest는 71개 통과, RAG DB 관련 10개 건너뜀이다.
- 확인 못 한 것: 기존 DB 볼륨 및 배포 DB 적용. 기본 계정 정보는 공개 데모 전용이다.

## 2026-11-02 로그인 역할 응답과 Compose 데모 계정
- 한 일: `/api/auth/me`가 DB에서 확인한 역할을 사용자 ID와 함께 반환하도록 변경했다. Compose 새 DB에서 DEMO 변수 네 개가 모두 비면 공개 데모 계정을 생성하고 네 값이 모두 있으면 해당 값을 사용한다. 일부 설정은 오류로 처리한다.
- 바꾼 파일: 인증 API와 테스트, 데모 시드, `.env.example`, README, SPEC, 로그인 작업서.
- 확인: 격리 Compose PostgreSQL에서 데모 관리자·사용자 로그인과 역할 응답을 확인하고 인증 통합 테스트를 실행했다.
- 확인 못 한 것: 기존 볼륨과 배포 DB의 시드 적용. 공개 데모 자격 증명은 실제 서비스나 제출용 계정으로 사용하지 않는다.

## 2026-10-30 Migration 1 SQL 초안
- 한 일: 최신 `db/table-definition.md`의 5.1~5.14를 기준으로 업무 테이블 14개, 기본키·CHECK·외래키·UNIQUE 및 정의서의 해시 인덱스를 담은 초안을 작성했다. 벡터 임베딩 Migration 2는 차원과 확장 스키마가 결정되지 않아 제외했다.
- 바꾼 파일: `db/001_create_business_tables.sql.draft`, `db/DB.md`, `docs/worklog/STH.md`
- 실행한 명령과 결과: 로컬 `STH`를 `main`까지 fast-forward했다(원격 변경 없음). 이력 결과 `STH`는 `origin/STH`보다 9개 커밋 앞섰다. SQL은 아직 DB에 적용하지 않았다.
- 확인 못 한 것: `db/ERD.md` 승인, migration runner 및 이력 테이블 선택, Supabase/Compose 양쪽 실행, IDENTITY 방식, `updated_at` 갱신 주체, 일부 가정 제약조건.
- 다음 할 일: 초안과 위 결정 항목을 검토·확정한 뒤 선택한 runner에 맞는 migration 경로로 옮겨 빈 로컬 DB 및 개발 DB에서 검증한다.

## 2026-10-30 Langfuse Cloud 연결 확인
- 한 일: `STH` 브랜치에서 Langfuse SDK v5 환경변수 호환과 자격증명 확인 함수를 추가했다. 자동 프롬프트·응답 계측은 보류했다.
- 바꾼 파일: `backend/services/llm.py`, `.env.example`, `backend/services/SERVICES.md`, `SPEC.md`, `docs/worklog/STH.md`
- 실행한 명령과 결과: `.env` 자격증명 값을 출력하지 않고 Cloud `GET /api/public/projects`를 호출해 인증 성공과 프로젝트 1개를 확인했다.
- 확인 못 한 것: Python SDK 함수 실행과 모델 trace는 검증하지 않았다. 현재 `.env`에 `OPENROUTER_API_KEY`가 없고, 이 셸에서 `uv`와 프로젝트 `.venv`를 찾지 못했다.
- 다음 할 일: 프롬프트·응답을 Cloud에 저장할지 결정되면 실제 LLM 계측을 추가한다.

## 2026-10-30 Migration 초기화 SQL 순서 정렬
- 한 일: Docker Compose 초기화 SQL에서 pgvector 확장이 업무 스키마보다 먼저 실행되도록 세 자리 파일명 규칙을 적용했다.
- 바꾼 파일: `db/01_init.sql`을 `db/000_init.sql`로 이동하고 `db/DB.md`, `docs/worklog/STH.md`를 갱신했다.
- 실행한 명령과 결과: 파일명 정렬과 Git diff를 확인했다. 실제 DB 초기화는 실행하지 않았다.
- 확인 못 한 것: 빈 DB에서 Compose 초기화, Supabase 적용, Migration 1/2 실행 이력은 검증하지 않았다.
- 다음 할 일: 피드백 2번의 `thread_id` 생성 규칙을 확정한 뒤 초안에 반영한다.

## 2026-11-02 Migration 1 코퍼스 정의 중복 정리
- 한 일: Migration 1 초안에서 PR #17 코퍼스 SQL과 중복된 문서·청크 표 및 청크 해시 인덱스 생성 정의를 제거하고 선행 조건을 기록했다. 기존 외래 키는 유지했다.
- 바꾼 파일: `db/001_create_business_tables.sql.draft`, `db/DB.md`, `db/table-definition.md`, 이 파일.
- 실행과 결과: 격리된 Compose PostgreSQL에서 pgvector 확장, PR #17 코퍼스 SQL, 수정된 초안을 순서대로 적용했다. 전체 15개 표와 문서·청크 참조 외래 키 6개를 확인했다. 원본 초안은 같은 조건에서 `source_documents` 중복으로 실패했고 트랜잭션이 롤백됐다. 검증 중 중지된 테스트 컨테이너를 재시작하고 동일 검증을 다시 수행했다.
- 확인 못 한 것: 실제 코퍼스 데이터가 있는 DB, Supabase, 마이그레이션 이력 도구와 자동 초기화 순서. PR #17은 현재 STH에 아직 반영되지 않았다.
- 다음 할 일: 팀의 최신 변경을 반영하고 ERD 및 SQL 실행 순서·이력 방식을 확정한 뒤 데이터가 있는 환경을 검증한다.

## 2026-11-02 로그인 및 사용자 식별 1차 구현
- 한 일: 기존 로그인 시안을 FastAPI에 연결하고 PostgreSQL 사용자·서버 세션, scrypt 비밀번호 해시, 동일 출처 확인, 계정별 로그인 실패 제한을 추가했다. 사전 생성 계정은 대화형 명령으로 준비한다. Migration 1 초안의 users 중복 정의를 인증 SQL로 이동했다.
- 바꾼 파일: `backend/auth.py`, `backend/main.py`, `backend/web/login.html`, `backend/web/WEB.md`, `db/03_auth.sql`, `db/001_create_business_tables.sql.draft`, `db/DB.md`, `db/ERD.md`, `db/table-definition.md`, `docs/specs/login-auth.md`, `docs/specs/SPECS.md`, `tests/test_auth.py`, `tests/TESTS.md`, `SPEC.md`, `.env.example`, `README.md`, 이 파일.
- 검증: 테스트 전용 PostgreSQL 컨테이너에 인증 SQL을 적용하고 `TEST_AUTH_DATABASE_URL`을 지정해 `.venv/Scripts/python.exe -m pytest -q`를 실행했다: 30 passed, 2 skipped. 두 계정의 로그인·세션·로그아웃·만료와 5회 실패 제한을 확인했다. 브라우저에서 테스트 계정 로그인과 로그아웃을 확인했다. `uv` 실행 파일은 현재 셸에서 찾지 못해 기존 프로젝트 가상환경의 Python을 사용했다.
- 미구현·미검증: 기존 DB·Supabase·Cloud Run에 스키마 적용 및 배포, 사용자별 회로·대화·기억·견적 접근 제어, 계정 생성 자동화·비밀번호 재설정, 대규모 악용 방어와 운영 보안 검토, 실제 평가 계정 준비, 평가셋 재측정. CI에서는 인증 통합 DB가 제공되지 않으면 해당 테스트를 건너뛴다.
- 다음 할 일: 팀과 기존 DB 마이그레이션 이력·실행 순서를 확정하고, AUTH_ORIGIN과 쿠키·자원 한도를 배포 환경에서 검증하며, 각 기능 구현 시 사용자 소유권 검사를 연결한다.

## 2026-11-02 최신 main 반영 및 로그인 작업 복원
- 한 일: 미커밋 로그인 변경을 untracked 파일까지 stash에 보관하고 `main`을 `git pull --ff-only`로 갱신했다. `STH`에 최신 main을 fast-forward한 뒤 보관한 변경을 다시 적용했다. `SPEC.md`와 `tests/TESTS.md`는 자동 병합됐으며 미해결 충돌은 없다. 보관본은 유지했다.
- 확인: 새 로그인 파일 4개의 Git 해시가 보관본과 일치하고 `git diff --check`에 오류가 없다. 격리 인증 DB를 사용해 `.venv/Scripts/python.exe -m pytest -q`를 다시 실행한 결과 31 passed, 2 skipped. 테스트 DB 컨테이너는 정지했다.
- 남은 일: 기존 DB 마이그레이션, 실제 사용자별 업무 데이터 접근 제어, 배포 보안 확인 및 평가셋 재측정은 수행하지 않았다.

## 2026-11-02 DB 폴더 안내 중복 정리
- 한 일: `db/DB.md`에서 중복된 Migration 1 목록과 존재하지 않는 `01_init.sql` 항목을 제거하고 현재 SQL 파일 및 실행 순서와 대조했다. 기존 볼륨에 초기화 SQL이 자동 재실행되지 않는 점과 볼륨 삭제 시 데이터가 사라지는 점을 명시했다.
- 확인: `db/` 파일 목록 및 SQL 초안의 선행 조건과 문서를 대조했다. DB 실행이나 볼륨 삭제는 하지 않았다.

## 2026-11-02 DB SQL 파일 번호 정리
- 한 일: 실행 순서에 맞춰 `02_rag_corpus.sql` → `002_rag_corpus.sql`, `03_auth.sql` → `003_auth.sql`, 업무 초안 `001_create_business_tables.sql.draft` → `004_create_business_tables.sql.draft`로 이름을 정리했다. 관련 코드·테스트·문서 경로를 갱신하고 `001`은 비워 뒀다. 코퍼스·임베딩 SQL은 삭제하지 않았다.
- 확인: Git 이력에서 별도의 `db/002*` SQL 삭제 기록은 찾지 못했다. 기존 두 자리 `02_rag_corpus.sql`이 코퍼스 및 임베딩을 생성한다. 각 SQL의 실행문은 변경 전과 같고 주석·파일명만 바뀌었다.
- 검증: 테스트 컨테이너의 별도 빈 DB에서 `000` → `002` → `003` → `004` 초안을 순서대로 수동 적용해 테이블 17개를 확인했다. 별도 DB에 `TEST_DATABASE_URL`, `TEST_AUTH_DATABASE_URL`을 지정하고 `.venv/Scripts/python.exe -m pytest -q` 실행: 32 passed, 1 skipped. 적재 테스트는 테스트 전용 DB에서 임시 스키마를 만들고 삭제했다.
- 확인 못 한 것: 실제 Compose 신규 볼륨 자동 초기화, 기존 팀원 DB·Supabase의 파일명 기반 이력과 데이터, 평가셋 재측정. 파일명 변경이 기존 마이그레이션 도구의 이력에 미치는 영향은 도구와 환경 확정 후 확인한다.

## 2026-11-02 인증·DB 적용·CI 1차 보강
- 한 일: 인증된 사용자 ID와 thread·Store·업무 데이터 소유권의 연결 계약 및 교차 접근 테스트 초안을 기록했다(팀 검토 필요). 실제 그래프·업무 API는 아직 없어 소유권 기능은 구현하지 않았다. 기존 DB의 인증 스키마를 읽기 전용으로 대조하는 절차를 추가했다.
- 한 일: PR CI에 격리 PostgreSQL과 인증 SQL 초기화를 추가했다. 로그인 실패 집계를 15분으로 한정하고 5회 실패 후 15분 잠금 정책을 유지했다. 기존 잠금 의미를 보존하기 위해 새 `005_auth_attempt_window.sql`로 집계 시작 컬럼을 추가했다.
- 검증: 실패 집계 시간이 없는 기존 코드에서 테스트 실패를 확인한 뒤 수정 후 통과했다. 격리 PostgreSQL 16에서 CI와 같은 인증 SQL 초기화 후 전체 테스트 33 passed, 2 skipped(코퍼스 DB 미설정). 기존 사용자·세션·활성 잠금이 있는 별도 모의 DB의 데이터 보존을 확인했다. DB 점검 SQL과 CI YAML 구조를 확인했다. GitHub Actions 실행은 아직 확인하지 않았다.
- 로컬 개발 DB: 대상 스키마와 제약을 격리 기준 DB와 읽기 전용 비교한 뒤 `005`만 트랜잭션으로 적용했다. 적용 전후 users 4건·sessions 1건·login attempts 0건이 유지됐고, 기존 로컬 테스트 계정 두 개로 변경된 코드의 로그인·식별·로그아웃을 확인했다. 공유 DB와 Cloud에는 적용하지 않았다.
- 남은 일: 실제 업무 데이터의 소유권 적용·교차 접근 테스트, 팀의 thread/Store ID 계약, 계정 잠금 악용·분산 요청·실패 기록 보존 대책, 실제 GitHub Actions 및 Cloud 배포 검증, 기존 DB 마이그레이션 이력 방식 확정, 평가셋 재측정. 과거 실패 기록 중 집계 시작 시간이 없는 비잠금 기록은 다음 실패부터 새 구간을 시작하며 활성 잠금은 유지된다.

## 2026-11-02 인증 리뷰 경계·동시 제한 검증 보강
- 한 일: 비활성 계정 및 비활성 사용자의 기존 세션 거부, 30분 유휴·8시간 절대 만료 경계 전후, 15분 잠금 중 차단과 잠금 종료 후 허용, 두 PostgreSQL advisory 슬롯 점유 시 503 테스트를 추가했다. HTTPS Secure 쿠키·교차 Origin 로그아웃·DB 오류 상세 미노출 테스트도 포함했다.
- 검증: 별도 CI 전용 PostgreSQL 16 (`sojafit-ci-auth-check`, 127.0.0.1:55434)에서 `TEST_AUTH_DATABASE_URL` 지정 후 `.venv/Scripts/python.exe -m pytest -q tests/test_auth.py`: 12 passed. 기존 로컬 개발 DB와 계정은 사용하지 않았다.
- 제한: 만료 경계는 DB 시각을 기준보다 5초 안팎 앞/뒤로 설정해 시험했으며 8시간을 실제 기다린 시험은 아니다. 두 advisory 잠금 점유 테스트는 초과 요청의 503 제한을 검증하지만, Cloud Run 프로세스의 실제 RSS나 scrypt 병렬 메모리는 측정하지 않았다.

## 2026-11-02 관리자·사용자 계정 권한
- 한 일: `006_user_roles.sql`로 기존 계정 기본 역할 `user`를 추가하고 신뢰된 명령줄에서 `admin` 생성 옵션을 제공했다. 관리자 전용 계정 조회·일반 계정 활성화 API와 로그인 화면을 추가했다. 일반 사용자의 관리자 API 접근과 관리자 계정의 상태 변경은 거부한다. 사용자 비활성화와 세션 삭제를 한 트랜잭션에서 처리하고 로그인과 비활성화가 사용자 행 잠금으로 경합하도록 했다.
- 변경: `backend/auth.py`, `backend/main.py`, `backend/web/login.html`, `db/006_user_roles.sql`, CI 초기화, 인증 테스트, `SPEC.md`, 인증 작업서·DB 안내·ERD·README·테스트 안내.
- 검증: 새 역할 컬럼이 없는 상태에서 새 관리자 테스트가 실패하는 것을 확인한 후 구현했다. 격리 PostgreSQL에서 전체 테스트 39 passed, 2 skipped. 새로 만든 임시 테스트 DB에 003→005→006 적용 후 인증 테스트 13 passed, 임시 DB만 삭제했다. 기존 `.venv` Python을 사용했으며 `uv` 명령은 PATH에서 찾지 못했다.
- 로컬 개발 DB: 사전 상태 사용자 4명·세션 2건을 확인하고 006을 적용했으며 기존 계정은 `user`로 유지했다. 별도 로컬 관리자·사용자 테스트 계정 2개를 생성하고 HTTP로 관리자 조회 200·일반 사용자 거부 403·비활성 세션 거부 401·재활성화 후 이전 세션 거부 401을 확인했다. 기존 세션 두 건은 유지했다. 테스트 비밀번호는 저장소 밖 이 PC의 로컬 `.env`에만 보관했다.
- 미검증: 관리자 화면의 직접 브라우저 조작, 공유 DB·Cloud Run 마이그레이션과 배포, GitHub Actions, 업무 데이터 소유권과 전체 평가셋. 기존 DB에서는 앱 업데이트 전 006을 한 번만 적용해야 한다.

## 2026-11-02 최신 main 병합과 로그인 작업 복원
- 한 일: PR #22의 head가 기존 STH 커밋 `d981455`와 같음을 Git 참조로 확인했다. 미커밋 관리자 작업을 untracked 파일 포함 stash로 보관한 뒤 `origin/main`을 STH에 병합했다. `db/DB.md`와 `db/ERD.md`의 코퍼스 halfvec 안내와 인증 SQL 명명·역할 안내를 함께 보존했다.
- 후속 수정: main에서 들어온 RAG 저장소 테스트가 옛 `db/02_rag_corpus.sql` 경로를 사용하는 부분을 `db/002_rag_corpus.sql`로 맞추고, Windows SQL 파일 UTF-8 읽기 및 비밀번호가 생략되는 `db.info.dsn` 재연결을 수정했다.
- 검증: 테스트 전용 PostgreSQL 16과 별도 임시 pgvector DB를 사용했다. 첫 실행은 임시 DB의 확장 미설치 및 Windows 기본 인코딩, 두 번째 실행은 잠금 테스트의 비밀번호 없는 DSN으로 실패해 각각 원인을 수정했다. pgvector 확장 및 UTF-8 환경에서 동일 전체 검사 재실행: 73 passed, 1 skipped. 임시 DB는 삭제했다.
- 제한: GitHub 연결 도구는 PR #22에 404를 반환하고 gh CLI는 사용할 수 없어 PR 메타데이터는 확인하지 못했다. 원격 PR 상태·GitHub Actions·배포는 확인하지 않았으며 push하지 않았다. 기존 stash와 이번 보관 stash는 유지했다.

## 2026-11-02 인증 리뷰 실측 기록
- 한 일: STH `8dc9630` 기준으로 격리 PostgreSQL 16.15에서 두 계정의 로그인·세션 분리·로그아웃, 잠금·세션 만료 경계, 실제 scrypt 동시 실행과 프로세스 메모리를 측정하고 `docs/auth-login-verification.md`에 기록했다. `docs/DOCS.md`에 파일을 등록했다.
- 환경과 결과: Windows Python 3.12.10, FastAPI TestClient, 로컬 테스트 DB. 고정된 트랜잭션 시각에서 잠금 900초와 절대 만료 28,800초 및 경계 전·동일·후 상태가 기대와 같았다. 2개 scrypt 호출이 343.11ms 겹친 동안 세 번째 요청은 503이었다. Windows 프로세스 working set은 단일 요청 54.11→183.43MiB, 동시 2개 55.39→312.13MiB였다. 각 결과는 단일 실행이다.
- 실행: 프로젝트 `.venv/Scripts/python.exe`로 로컬 실측 스크립트 `auth_boundary_after_merge.py`, `measure_scrypt_concurrent.py`를 각각 격리 DB에 대해 실행했다. 실측 스크립트와 원시 JSON은 로컬 작업 폴더에만 보관했고 테스트 데이터는 롤백 또는 삭제했다.
- 제한: 메모리는 Windows Python 프로세스 표본이며 PostgreSQL·OS 메모리는 제외, Cloud Run·실제 경과 시간 대기·분산 인스턴스는 미검증. 반복 부하 및 GitHub Actions 결과도 별도 확인이 필요하다.

## 2026-11-02 로그인 테스트 화면 제거 및 Compose 데모 계정 시드
- 한 일: 수동 로그인·관리자 화면 HTML과 해당 루트 라우트를 제거하고, 로컬 `.env`의 이메일·scrypt 해시를 사용하는 Compose 초기화 SQL 시드를 추가했다. 자격 증명은 읽거나 저장소에 기록하지 않는다.
- 문서 보완: README의 상세 `.env` 설정 절차는 제거하고, 필요한 변수·해시 생성·따옴표 규칙을 `007_demo_accounts.sql` 주석으로 옮겼다. `.env.example`에는 변수 목록과 간단한 안내를 유지했다.
- 제한: 자동 시드는 새 Compose 볼륨의 최초 초기화에서만 실행된다. 네 환경변수가 모두 비어 있으면 건너뛰며, 기존 볼륨에는 자동 재실행되지 않는다.
- 검증: `uv run pytest tests/test_auth.py tests/test_health.py -q` 결과 8 passed, 8 skipped(로컬 테스트 인증 DB 미설정). 루트 회귀 테스트는 수정 전 HTML 응답 200으로 실패했다. 해시 전용 CLI 시험을 포함했다. `docker compose config --quiet` 통과. 이름이 분리된 새 Compose DB에서 임시 scrypt 해시로 관리자·일반 계정 생성과 해시 형식을 확인하고 DB 초기화 로그에 해시가 없는 것을 검사했다. 환경변수를 비운 별도 새 DB도 정상 기동하고 users 0건임을 확인했다. 두 격리 테스트 프로젝트의 볼륨만 삭제했으며 기존 개발 DB는 사용·변경하지 않았다. 별도 임시 `.env`로 작은따옴표로 감싼 scrypt 해시가 Compose 컨테이너 환경에 그대로 전달되는 것도 값 비공개 상태로 확인했다. `git diff --check`에서 공백 오류는 없고 줄바꿈 변환 경고만 표시됐다.

## 2026-11-02 인증 실측 재현 자료 추가
- 한 일: 인증 경계값·scrypt 측정 스크립트와 해당 실행의 원시 JSON을 `docs/`에 복사하고 실측 기록 및 문서 색인에 링크했다. 저장소 루트에서 실행할 수 있도록 스크립트에 repo 경로 준비를 추가했다.
- 안전 범위: 스크립트는 `TEST_AUTH_DATABASE_URL`에 `127.0.0.1:55434/ci_auth`가 있을 때만 실행한다. 실측 산출물에서 계정 비밀번호·세션 토큰·DB 접속 문자열은 확인되지 않았다. 재실행은 원시 JSON을 덮어쓴다.
- 확인: JSON 값과 문서 수치를 대조하고, 스크립트 문법을 검증한다. DB 실측은 새로 수행하지 않는다.

### 2026-11-03 웹 검색 후보 비교 준비
- 목적·조건: Tavily keyless, Exa 익명 MCP, Brave를 W02~W08 각 최대 1회 비교. 15초 제한, 재시도·본문 추출 없음, 실제 지출 $0. 불확실한 유료 계정은 호출하지 않음.
- 기대와 실패 처리: evals/PREREGISTER.md의 웹 검색 후보 탐색 항목 참조. 동결 평가셋은 사용하지 않음.
- 시작 전 상태: STH에서 git pull --ff-only 결과 최신; origin/main은 22커밋 앞섬. 기존 미커밋 문서는 보존.

- 실측 결과: Tavily 키 없는 SDK 7회 정상, Exa 익명 MCP 7회 중 정상 4·무료 제한 2·원본 기록 오류 1. Brave 결제 통제 미확인으로 미호출. 비용 . 상세와 축약 원자료는 후보 문서 9절 및 evals/results/web-search-exploration-2026-11-03.json. Tavily 실행기 추가. 프로젝트 MCP/서비스 연동과 Brave 측정은 미완료.

- 2026-11-03 Brave 추가 실측: 사용자가 무료 크레딧 $5와 자동 충전 비활성화를 확인. W02~W08 각 1회, 정상 7/7, 공식 도메인 출현 7/7, 응답 p50 669.14ms. URL·본문 미보관, 파생 통계 보관 허용 여부 및 실제 계정 크레딧 차감은 미확인.

- 2026-11-03 웹 검색 재측정 준비: 기존 결과를 알고 같은 W02~W08을 세 후보에 최대 한 번씩 재실행. 무료 경로·지출 , 15초, 재시도 없음. 기대·조건은 사전등록 참조.

- 2026-11-03 웹 검색 재측정: 21회 전부 정상. Tavily 공식 도메인 4/7·p50 790.22ms, Exa 6/7·p50 1,193.75ms, Brave 7/7·p50 240.48ms. Brave 응답 URL·본문 미보관, 파생 통계 보관 허용 범위와 실제 크레딧 차감은 미확인. 코드 경로의 차이와 이전 결과를 본 반복 실험 한계는 후보 문서 10절.

- 웹 검색 30문항 탐색: 기존 W01~W08을 제외한 manifest에서 seed 42로 30개를 무작위 추출해 입력과 사전 기대를 검색 전 고정. 각 도구 최대 30회, 실제 지출 $0, 재시도 없음.

- 30문항 실측: Tavily 정상 25 후 한도 1·미실행 4, Exa·Brave 각 정상 30. 과거 manifest 주소 일치는 각 2/25·22/30·9/30. URL·본문 없이 질의별 집계와 실행기를 evals에 기록, Brave 파생값의 보관 범위와 실제 크레딧 차감 미확인. 상세 후보 문서 11절.

- Tavily 인증 30문항 준비: 무료 크레딧 30 이상·초과 자동 과금 꺼짐을 사용자가 확인. 같은 30문항 Basic 각 1회, , 재시도 없음. 이전 결과를 이미 본 재측정임을 사전등록.

- Tavily 인증 30문항 실측: 정상 30/30, 도메인 28/30, 과거 주소 일치 3/30, 응답 p50 822.73ms. 키·URL·본문 없는 질의별 집계와 실행기 추가. 무료 크레딧 차감 내역은 대시보드에서 미확인.

- 웹 검색 실측 결과를 팀 공유용 web-search-results-interpretation.md로 정리. 30문항 결과표, 지표별 의미, 후보별 해석과 PDF·비용·호출 조건의 미확인 사항을 기록.


### 2026-11-03 MCP 검색 도구 1차
- main을 1cf18a9까지 fast-forward한 뒤 STH에 반영. 기존 웹 검색 문서·사전등록 복원 중 docs/README.md와 evals/PREREGISTER.md 충돌을 양쪽 내용 보존으로 해결했다. 보관 stash는 안전을 위해 남겼다.
- 작업서 docs/specs/mcp-search-tools.md, SPEC 8.7, FastMCP stdio 서버 두 도구, 환경변수 예시, 의존성·테스트를 추가했다. EXA_WEB_SEARCH_ENABLED 기본 0, 데모에서도 외부 호출을 차단하고 결과를 미검증 후보로 표시한다.
- uv run --no-sync pytest -q tests/test_mcp_search.py tests/test_rag_retrieve.py tests/test_graph_search.py: 31 passed, 1 skipped. stdio 응답 형식 차이로 첫 실행은 1 failed였고 응답 텍스트를 JSON으로 읽도록 고친 뒤 재실행해 통과했다.
- 실제 Exa API 호출·과금·PDF 검증·실제 DB 연동·LangGraph 연결·Compose/클라우드 배포 및 가산점은 미검증이다.

### 2026-11-03 웹 검색 도메인 필터 비교 준비
- 기존 30문항으로 도구별 무필터/필터 1회씩 짝 비교. 총 최대 180회, 결과 5개, 15초, 재시도 없음, 지출 $0.
- Exa Auto·Tavily Basic·Brave Search 각 인증 경로로 고정. Brave는 site 연산자를 쓰며 세 공급자의 필터 방식은 동일 구현이 아님. 무료 잔액과 자동 과금·충전 확인을 기다린다.

- 2026-11-03 TSC 필터 비교: 사용자 무료 잔액 및 자동 과금 차단 확인 후 Exa·Tavily·Brave 각 필터 없음/적용 30회씩, 총 180/180 정상. 기존 manifest 주소 일치는 Exa 23→24, Tavily 5→5, Brave 9→9. 실제 차감·청구 내역 미확인.
- 별도 사전등록한 S23·S13·S29 공개 PDF 각 1회 확인: 모두 PDF·기존 manifest 해시 일치, 문서명 문자열은 S29 미확인. PDF 원문 및 검색 응답 URL·본문은 저장하지 않음. 세부 결과 docs/web-search-filter-comparison.md.

- MCP 도구 목록과 후속 선행 조건을 docs/mcp-tool-implementation-plan.md에 정리했다. get_corpus_document를 추가해 기존 manifest의 문서 메타데이터를 읽기만 하고 PDF 미검증 상태를 표시한다. MCP·RAG 테스트 36 passed, 1 skipped; 실제 DB 및 외부 PDF 연동은 미검증.

- MCP 우선순위 1~2 실행 준비: 기존 계획에 5개 도구·기능의 현재 상태, 단계별 준비·검증·완료 기준, 팀 결정 항목 추가. MCP·RAG 테스트 36 passed, 코퍼스 DB 검사 1 skipped. Docker 엔진 접근 불가를 확인. 외부 API·DB 데이터 변경 없음.

### 2026-11-03 저장소 표본의 DB 없는 테스트 준비
- Git에 있는 PDF 3건·manifest·공개 회로 5종으로 MCP와 입력 읽기, PDF 파일·텍스트를 시험한다. 외부 요청·DB 연결·지출 0. 조건과 기대는 evals/PREREGISTER.md에 먼저 기록했다.

- 저장소 표본 DB 없는 점검: MCP·회로 읽기·수집·파싱 기초 31 passed; PDF 서명·manifest 해시·쪽 수 3/3 일치, 개정 코드·품번 토큰 3/3 발견, 전체 문서명 0/3. pypdf 오프라인 점검 스크립트·결과 문서 추가. Docling·pdfplumber, DB, 실제 Exa는 미실행.

### 2026-11-03 Docling·pdfplumber 표본 대조 준비
- 사용자 요청: 저장소 PDF 3건에 기존 파서를 DB 없이 실행하고 표 숫자를 양방향 대조한다. 금전 $0, 출력은 저장소 밖 사용자 작업공간. Windows 프로세스 외부에서 파일당 600초 제한.
- uv sync --locked --group ingest --offline: torch 캐시 부재로 실패. 이어서 uv sync --locked --group ingest 성공해 잠금된 74개 패키지를 프로젝트 가상환경에 설치했다. Docling 2.145.0, pdfplumber 0.11.10, torch 2.15.0.
- 예상·실행 조건은 evals/PREREGISTER.md에 사전등록. DB·LLM·유료 API를 사용하지 않는다.

- Docling·pdfplumber 실측: uv ingest 의존성을 설치한 후 저장소 TSC PDF 3건을 별도 사용자 작업공간에서 처리. 총 18쪽·표 18개, 표 셀 숫자의 같은 쪽 대조 515/515, 찾은 표 영역 역방향 숫자 누락 0. 대표 정격 3행의 좌표 영역을 별도 대조. 세 원본 해시는 사후에도 manifest와 일치. 파서·MCP 회귀 23 passed. 전체 표 누락·품번/조건 의미·실제 DB 연동은 미검증. 상세 docs/mcp-docling-verification-2026-11-03.md.

### 2026-11-03 MCP 외부 검색 개인정보 경계

- 사용자 결정: 공개 확인된 품번만 외부 검색하고 확인 불가 시 중단한다. 자유 문장 대신 TSC 공개 출처 manifest의 문서 ID를 받아 출처·문서명·개정이 일치할 때만 목록 값으로 검색어를 만든다. 목록 밖은 unverified, 목록 오류는 unavailable로 차단한다.
- 수정: MCP 서버, 검색 도구 작업서·SPEC·MCP 안내·구현 계획, 모의 테스트. 기존 질의 인자 query는 doc_id로 변경했다.
- 모의 테스트에서 변경 전 개인 정보가 포함된 문장이 외부 요청에 전달되려는 실패를 확인했다. 수정 후 `uv run --no-sync pytest -q -rs tests/test_mcp_search.py tests/test_mcp_manifest.py tests/test_rag_retrieve.py tests/test_graph_search.py` 결과 44 passed, 1 skipped (테스트 DB 미설정). 실제 Exa 호출 및 비용 발생은 없다.
- 제한: manifest는 과거 공개 출처 기록이며 실시간 공개 상태를 보증하지 않는다. 목록 밖 신규 품번 검색, 다른 외부 서비스의 정보 전송, 공급자의 로그·보관 정책은 검증하지 않았다.

### 2026-11-03 TSC 공개 품번 확인 방안 정리

- 코퍼스 밖 TSC 품번 조회와 외부 전송의 경계를 논의할 수 있도록 네 가지 방안, 장단점, 결정 항목을 docs/tsc-public-part-verification-options.md에 정리하고 docs/README.md에 연결했다. 팀 결정 전 초안이다.
- 코드·DB·API 변경이나 외부 API 호출은 없다. 출처 자료의 전체 품번 포함 여부, 자동 수집 조건과 제조사 API는 미확인이다.

### 2026-11-03 MCP 현황과 다음 작업 준비

- 현재 코드·문서·Skill 양식과 브랜치 상태를 대조하고 기존 MCP 구현 계획에 완료 범위, 검증 경계, 후속 순서를 정리했다.
- `uv run --no-sync pytest -q -rs tests/test_mcp_search.py tests/test_mcp_manifest.py tests/test_rag_retrieve.py tests/test_graph_search.py`: 44 passed, 1 skipped (테스트 DB 미설정). `docker compose ps`: Docker 엔진 소켓 부재로 연결 실패. 외부 API·DB 변경 없음.

### 2026-11-03 격리 DB MCP 검색 점검

- 임시 pgvector PostgreSQL 16.15에 합성 문서 4건·청크 8건을 넣고 데모 BM25 및 stdio MCP 경로를 확인했다. 일반 실행의 첫 검색이 지연됐으며 추적상 NumPy import에 머물렀다. 진단용 사전 import 조건에서만 알려진 품번 2건, 미존재 품번 0건, 다른 품번 필터 0건, manifest found, 웹 disabled를 확인했다. 실제 코퍼스 및 원인 검증은 미완료. 상세와 단발 측정치는 docs/mcp-tool-implementation-plan.md 참조. 기존 DB·외부 API는 사용하지 않았다.
### 2026-11-03 우선순위 2 MCP 도구 골격

- `verify_tsc_pdf(doc_id)`와 `get_circuit_info(circuit_id, target)`를 MCP 도구 목록에 추가했다. 두 도구는 입력 형식만 확인하고 `not_implemented`를 돌려주며 네트워크·파일·DB에 접근하지 않는다.
- MCP 작업서와 폴더 안내, 구현 계획에 미구현 상태와 선행 결정 사항을 명시했다. 검색 지연 조사는 미해결이라 그 로직은 수정하지 않았다.
- 이번 요청에서는 테스트 실행을 하지 않았다. 변경 검토는 diff 확인으로 제한한다.

### 2026-11-03 최신 main 통합

- `origin/main`의 17개 커밋을 로컬 `STH`에 병합했다. `docs/specs/README.md`와 `evals/PREREGISTER.md` 충돌은 MCP 검색·웹/PDF 기록과 main의 Skill·도구 프롬프트 기록을 모두 보존해 해결했다.
- 저장소의 동결 평가셋 blob은 CRLF이고 `FROZEN.json`은 LF 바이트 해시를 기록해 Windows에서 검사가 실패하는 문제를 확인했다. 평가셋 내용이나 기대 해시는 바꾸지 않고 `.gitattributes`에서 `evals/dataset_v*.jsonl`을 항상 LF로 체크아웃하게 했다.
- UTF-8 임시 JSON을 Windows 기본 cp949로 읽던 테스트 2곳에 인코딩을 명시했다. `uv run --no-sync pytest -q` 재실행 결과 184 passed, 24 skipped.
- 원격 push, 외부 API 호출, DB 변경은 수행하지 않았다.

### 2026-11-03 MCP `search_corpus` LangGraph 통합 설계

- 두 사람 분담안의 B 역할에 맞춰 범위를 MCP 서버 구현이 아닌 LangGraph 검색 통합으로 확정했다. 나머지 도구 4개의 사용자 흐름 연결, 서버 계약 변경, 외부 실호출은 제외했다.
- `docs/specs/mcp-graph-integration.md`에 동기 그래프와 비동기 stdio 세션의 경계, 정상 빈 결과와 MCP 장애 구분, 세션 재사용·종료, 가짜 클라이언트와 격리 DB 검증 AC를 작성했다.
- 서버 코드·공통 SPEC·테스트·동결 평가셋은 변경하지 않았다. 구현 전 사용자 문서 검토를 기다린다.

- 작업서 승인 후 `docs/specs/mcp-graph-integration-plan.md`에 6개 구현 작업을 TDD 순서로 작성했다. 그래프 장애 분기, 응답 검증, 지속 stdio 세션, 그래프 재검색, 격리 DB, 문서·변이 검증을 각각 독립 커밋으로 나눈다. 구현 코드는 아직 변경하지 않았다.

### 2026-11-03 MCP `search_corpus` LangGraph 통합 구현

- B 담당 범위에서 `backend/graph/mcp_retriever.py`를 추가하고 기존 `build_graph(retriever=...)`에 주입했다. stdio MCP 세션은 전용 asyncio 루프에서 한 번 열어 재사용하며, 응답 청크 필드·타입을 검사한다. A 담당 `backend/mcp_skill/` 서버 코드는 수정하지 않았다.
- 정상 빈 목록은 기존 문서 없음으로, MCP timeout·도구 오류·응답 형식 오류는 `retrieval_error`로 구분해 채점·재검색 없이 안전한 장애 응답으로 끝낸다. 직접 RAG 기본 경로와 검색 최대 2회는 유지했다.
- TDD 커밋: `3eb7d40` 검색 장애 분기, `bba9c4f` 응답 검증, `5d28e6f` 지속 stdio 세션, `a989b57` 그래프 재검색 통합, `e7b8c70` 조건부 실제 stdio 검사.
- 변이 확인 3건은 검색 상한 2→3, 장애를 빈 결과로 변경, 장애를 채점으로 분기했을 때 각각 지정 테스트가 실패했고 원복 후 통과했다. 상세는 `docs/GATES.md`.
- `uv lock --check` 통과. `uv run --no-sync pytest -q -rs` 결과 196 passed, 25 skipped. 신규 `tests/test_graph_mcp_stdio.py`는 `TEST_DATABASE_URL` 미설정으로 skip되어 실제 그래프→stdio MCP→격리 DB 경로와 단발 지연은 이번 환경에서 확인하지 못했다.
- 외부 API·LLM 실호출, 운영 DB, Docker 볼륨 변경, 나머지 MCP 도구 4개의 그래프 연결은 수행하지 않았다. 원격 push·PR 생성도 수행하지 않았다.

### 2026-11-03 최신 main 재통합

- `origin/main` `5760105`를 로컬 `STH`에 병합했다. 기존 MCP·LangGraph 커밋은 유지하고, `backend/mcp_skill/mcp_server/server.py`의 도구 5종 구현과 `search_corpus` 그래프 연결을 보존했다.
- main의 ADR 0012 폴더 규칙에 맞춰 충돌한 설명 파일을 `GRAPH.md`, `MCP_SKILL.md`, `DOCS.md`, `SPECS.md`, `SCRIPTS.md`에 통합했다. MCP 조사·실측 문서 7개는 `docs/research/`로 옮기고 링크·`SOJAFIT.md` 트리·폴더 파일 목록을 갱신했다.
- main의 턴 초기화와 합쳐질 때 이전 MCP 장애가 남지 않도록 `read_input`이 `retrieval_error`도 초기화하게 하고 회귀 테스트를 추가했다. Windows에서 저장소 구조 테스트가 Git UTF-8 파일 목록을 cp949로 읽던 문제는 subprocess에 `encoding="utf-8"`을 명시했다.
- `uv lock --check` 통과. MCP·그래프 집중 테스트는 `64 passed, 1 skipped`, 전체 `uv run --no-sync pytest -q -rs`는 `209 passed, 25 skipped`였다.
- `TEST_DATABASE_URL`과 인증 전용 테스트 DB가 없어 실제 stdio MCP→격리 DB 및 DB 의존 테스트는 실행하지 못했다. 원격 push·외부 API·운영 DB 변경은 수행하지 않았다.

### 2026-11-03 PR #44 계약 수용과 B 연결 조정

- A 확인에 따라 원격 PR #44 head `0185d55`를 로컬 B 커밋과 병합하고, 이어 최신 `origin/main` `72b7723`의 폴더·평가 변경을 통합했다. PR #44가 저장소 밖 보관으로 정한 MCP 독립 테스트·웹 측정 파일 삭제를 유지했고, B 그래프 테스트는 새 구조인 `tests/graph/`로 옮겼다.
- PR #44의 stdio 관찰 계약인 `structuredContent={"result": [...]}`를 먼저 실패 테스트로 고정했다. 기존 디코더에서 청크 목록과 빈 목록이 모두 `invalid_response`로 실패하는 것을 확인한 뒤, `structuredContent.result`를 우선 검증하고 이전 단일 JSON 텍스트는 호환 경로로 남겼다. 해당 테스트 파일은 `13 passed`였다.
- PR #44·B 문서와 최신 main의 검색 베이스라인·시장 조사 문서를 모두 보존하고 `SOJAFIT.md`, 폴더 설명, B 작업서의 새 경로를 맞췄다. 구조 검사는 `5 passed`, 그래프 묶음은 `58 passed, 1 skipped`, 전체 회귀는 `190 passed, 25 skipped`, `uv lock --check`는 통과했다.
- 일회용 pgvector DB에 합성 문서 4건·청크 5건을 넣어 실제 stdio를 재검증했다. 기본 서버 경로는 10초 제한에서 `timeout`, PR #44에 기록된 `numpy` 선행 import 진단 경로는 4.51초에 청크 2건과 `SS32 SERIES_Q2412.pdf` 출처를 정상 수신했다. 일회용 컨테이너는 제거했다.
- 결론: B의 실제 FastMCP 응답 해석은 조정됐지만, 기본 MCP 서버의 첫 검색 지연은 A 서버 초기화 범위로 남는다. 원격 push·외부 API·운영 DB 변경은 수행하지 않았다.

### 2026-11-03 MCP 첫 검색 지연 개선

- 사용자 결정에 따라 검색 지연을 B 통합 범위에서 직접 개선했다. 격리 DB의 실제 LangGraph → stdio MCP 테스트에 첫 검색 10초 제한을 먼저 추가했고, 변경 전에는 `1 failed in 13.60s`로 재현됐다.
- 원인은 FastMCP 요청 worker에서 처음 실행되던 NumPy 지연 import였다. 공용 검색 모듈 시작 시 NumPy를 읽도록 옮겼으며 MCP 서버 계약과 도구 구현은 변경하지 않았다.
- 같은 합성 DB에서 수정 후 통합 테스트는 `1 passed in 3.58s`, 별도 측정은 프로세스 시작부터 첫 청크 2건까지 2.426초, 같은 세션의 두 번째 검색은 0.045초였다. 이는 합성 문서 4건·청크 5건의 로컬 단발 측정이며 실제 전체 코퍼스의 운영 성능을 뜻하지 않는다.
- MCP·검색 집중 테스트는 `26 passed in 3.80s`, `uv lock --check`와 전체 회귀는 `201 passed, 14 skipped`였다. 외부 API·LLM·운영 DB·원격 저장소는 사용하거나 변경하지 않았다.
