# 로그인·세션·scrypt 로컬 실측

- 상태: 이력
- 기준일: 2026-11-02
- 기준 커밋: 8dc9630 (측정 대상 코드). 현재 코드와 다른 점은 5절
- 정본 여부: 비정본(측정 기록). 인증 동작의 정본은 `backend/auth.py`와 [SPEC.md](../../SPEC.md)
- 관련 문서: [auth-feedback-key-verification.md](auth-feedback-key-verification.md), [scripts/auth/AUTH.md](../../scripts/auth/AUTH.md), [login-auth 스펙](../specs/login-auth.md)

## 1. 질문과 결론

질문: 두 계정의 세션이 분리되는가, 잠금·만료 경계가 설정대로인가, 동시 비밀번호 검증의 메모리가 얼마인가.

| 항목 | 값 | 근거 |
|---|---|---|
| 세션 분리 | 계정 A 로그아웃 후 A 401, B 200. B 로그아웃 후 B 401 | `scripts/results/auth/scrypt_concurrent_2026-11-02.json` `two_concurrent.result.session_checks` |
| 로그인 잠금 | 잘못된 비밀번호 5회째에 잠금, 잠금 길이 900초 | `scripts/results/auth/auth_boundary_2026-11-02.json` `lock_duration_seconds`, `steps` |
| 세션 절대 만료 | 28,800초(8시간) | 같은 파일 `session_absolute_duration_seconds` |
| scrypt 1건 메모리 증가 | working set 129.32 MiB, private bytes 129.66 MiB | `scrypt_concurrent_2026-11-02.json` `single` |
| scrypt 2건 동시 메모리 증가 | working set 256.74 MiB, private bytes 257.36 MiB | 같은 파일 `two_concurrent` |
| 3번째 동시 로그인 | 503, 10.52 ms | 같은 파일 `third_status_during_both_scrypt_calls`, `third_request_ms` |

## 2. 방법과 환경

| 항목 | 값 |
|---|---|
| 환경 | Windows 11, Python 3.12.10, FastAPI 0.162.0, PostgreSQL 16.15(Docker, 테스트 전용) |
| 호출 방식 | FastAPI `TestClient`를 Windows 단일 프로세스에서 실행. PostgreSQL은 localhost TCP. 브라우저·외부 네트워크 없음 |
| 계정 | 무작위 임시 계정. 종료 후 해당 계정·세션·실패 기록만 삭제. 비밀번호·세션 토큰은 기록하지 않음 |
| 경계 시험 | PostgreSQL 한 트랜잭션의 `CURRENT_TIMESTAMP`를 고정하고 롤백. 15분·30분·8시간을 실제로 기다리지 않음 |
| 메모리 시험 | `scrypt(n=131072, r=8, p=1)` 실제 실행. Windows `GetProcessMemoryInfo`로 API와 TestClient가 함께 도는 Python 프로세스를 2 ms 간격 목표로 표본 추출 |
| 측정 시각(KST) | 경계 시험 2026-11-02 15:53:30, 메모리 시험 15:55:15 |
| 같은 날 전체 회귀 | 테스트 전용 PostgreSQL과 임시 pgvector DB, UTF-8 모드의 `pytest -q`: 73 passed, 1 skipped. GitHub Actions 결과가 아님. 원시 파일 없음 |

## 3. 결과

### 3.1 두 계정 세션 분리

| 요청 | 기대 | 관측 |
|---|---:|---:|
| A 로그인 / B 로그인 | 각 200 | 각 200 |
| A 사용자 확인 / B 사용자 확인 | 각 200 | 각 200 |
| A 로그아웃 후 A 사용자 확인 | 401 | 401 |
| A 로그아웃 후 B 사용자 확인 | 200 | 200 |
| B 로그아웃 후 B 사용자 확인 | 401 | 401 |

범위: 인증 세션 분리만 확인한다. 회로·대화·장기 기억·견적 데이터의 사용자 간 접근 차단은 시험하지 않았다.

### 3.2 잠금과 세션 만료 경계

원시: `scripts/results/auth/auth_boundary_2026-11-02.json` `steps` 14행. 잘못된 비밀번호 1~5회는 모두 401이고, 1~4회에는 잠금 시각이 없다.

| 조건 | 경계 1 μs 전 | 정확한 경계 | 경계 1 μs 후 |
|---|---:|---:|---:|
| 15분 잠금 종료, 올바른 비밀번호 | 401 | 200 | 200 |
| 30분 비활동 세션 | 200 | 401 | 401 |
| 8시간 절대 만료, 최근 활동 유지 | 200 | 401 | 401 |

`CURRENT_TIMESTAMP`는 트랜잭션 시작 시각이다. 실제 요청에서 DB 대기나 scrypt 시간이 길면 응답 완료 시각부터 잰 유효 시간과 차이가 날 수 있다. 위 표는 고정된 DB 시각에서의 비교다.

### 3.3 scrypt 동시 실행 메모리

표본 수는 단일 29개, 동시 35개다. 원시: `scripts/results/auth/scrypt_concurrent_2026-11-02.json`.

| 측정 | 실행 전 working set | 표본 중 최대 | 증가량 | 실행 전 private bytes | 표본 중 최대 | 증가량 |
|---|---:|---:|---:|---:|---:|---:|
| 로그인 1건 | 54.11 MiB | 183.43 MiB | 129.32 MiB | 39.93 MiB | 169.59 MiB | 129.66 MiB |
| 로그인 2건 동시 | 55.39 MiB | 312.13 MiB | 256.74 MiB | 41.13 MiB | 298.48 MiB | 257.36 MiB |

동시 2건은 모두 200이고 scrypt 실행 구간이 343.11 ms 겹쳤다. 두 건이 실행되는 동안 세 번째 로그인은 503으로 거부됐다. 두 건을 동시에 시작하려고 잠금 획득 후 검증 직전에 동기화 대기를 넣었으므로 전체 응답 시간(약 376 ms)은 서비스 지연으로 해석하지 않는다.

## 4. 결정에 미치는 영향

로그인 경로의 동시 scrypt 검증은 PostgreSQL 트랜잭션 advisory lock 2칸(`backend/auth.py:339`)으로 2건까지 허용한다. scrypt 한 건당 128 MiB 근거는 `backend/auth.py:37`의 주석이다. 이 제한은 같은 DB와 로그인 경로를 공유할 때만 적용된다. 계정 생성 명령의 scrypt는 범위 밖이다.

## 5. 현재 코드와 다른 점

| 항목 | 이 측정 | 현재 코드 |
|---|---|---|
| 비활동 세션 만료 | 30분 | 2시간(`backend/auth.py:483`, `last_seen_at > CURRENT_TIMESTAMP - INTERVAL '2 hours'`). 3.2절의 30분 행은 현재 코드에 맞지 않는다 |
| 로그인 실패 한도 | 계정당 5회 | 계정당 5회(`backend/auth.py:366`)에 IP당 30회(`LOGIN_IP_FAILURES`, `:41`) 한도가 추가됨 |

## 6. 한계

- 단일 PC의 단일 실행이다. 서비스 전체 메모리, Cloud Run 성능, 공식 평가 결과가 아니다.
- 메모리 표본은 2 ms 목표 간격이며 실제 최고점을 놓칠 수 있다. PostgreSQL 컨테이너와 OS 전체 메모리는 포함하지 않는다. 증가량에는 Python·요청 처리의 다른 메모리 변화가 섞여 있다.
- DB 연결이 검증 중 끊겨 잠금이 먼저 풀리는 경우의 프로세스 메모리 상한은 확인하지 않았다.
- 미측정: Cloud Run 실제 메모리 설정·인스턴스 수·지연·오류, 반복 부하, GitHub Actions의 인증 DB 테스트 실행 여부, 실제 서비스 데이터의 계정 간 접근 차단.

## 7. 재현

```powershell
uv run python scripts/auth/auth_boundary_after_merge.py
uv run python scripts/auth/measure_scrypt_concurrent.py
```

- 사전 조건: 격리된 테스트 전용 PostgreSQL과 `TEST_AUTH_DATABASE_URL`(값에 `127.0.0.1:55434/ci_auth` 포함). 포함되지 않으면 스크립트가 실행되지 않는다.
- 메모리 스크립트는 Windows `GetProcessMemoryInfo`를 쓰므로 Windows에서만 실행된다.
- 경계 스크립트는 트랜잭션을 롤백하고, 메모리 스크립트는 자신이 만든 임시 계정만 정리한다.
- 결과는 `scripts/results/auth/`에 측정 날짜(KST)를 붙인 JSON으로 쓰이며, 같은 날 다시 실행하면 덮어쓴다.
