# 실행 기록
- 일시: 2026-11-13 01:57~02:10 KST. 대상 `origin/main` = `b5f050d` (git fetch origin 후 확인, 총 948 커밋/비병합 801). 로컬 `jeongun` 트리 해시 동일(5553cd08).
- gitleaks: `v8.30.1`, 이미지 `ghcr.io/gitleaks/gitleaks:latest` -> `ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f` (docs/worklog/sth.md:566의 11-09 기록과 같은 digest). 워크플로(.github/workflows/secret-scan.yml)는 `:latest` 고정 없음, `detect --source /repo --no-banner --redact -v`, 설정 `.gitleaks.toml`/`.gitleaksignore`는 저장소 루트에서 자동 로드.
- 래퍼 `gl.sh <src> <args>`: `docker run --rm -v <src>:/repo:ro -v <out>:/out -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/repo <image@digest> <args>`
- 2a: `gl.sh <live repo> git /repo --no-banner --redact --log-opts="origin/main" -r /out/2a_full_history.json -f json` -> 801 commits scanned, 0
- 2b: 같은 명령 `--log-opts="db77a11..origin/main"` -> 207 commits scanned, 0. 기준 db77a11 = 11-11 06:17 "gitleaks 오탐 두 곳 허용"(0건을 얻은 설정 커밋; 기록 커밋 19bd964 바로 앞). 범위 246 커밋(병합 포함).
- 2c: `git archive origin/main | tar -x -C <scratch>/export` 후 `gl.sh <export> dir /repo --no-banner --redact -r /out/2c_worktree.json -f json` -> 9건 (모두 알려진 허용 항목, 경로 앵커 때문에 dir 모드에서만 보임)
- 2d: 설정·무시 목록이 없는 깨끗한 bare 저장소(`git init --bare` + 로컬 `git fetch <repo> refs/remotes/origin/main:refs/heads/main`)에 `gl.sh <bare> git /repo --no-banner --redact --log-opts="main" -r /out/2d_no_ignore.json -f json` -> 801 commits, 1366건 (먼저 `-c`/`-i` 옵션으로 시도했더니 저장소 .gitleaksignore가 계속 적용돼 1365건이어서 bare 방식으로 교체).
- 추가 검사: `python3 -I tools/pat.py <export> <bare> d10/secrets/pat` (export 전 파일 + `git log -p -U0 main` 추가 줄). 결과 pat_files.json / pat_hist.json (값은 앞 4자만).
- 컨테이너는 --rm으로 종료 후 자동 삭제. 접근하지 않은 것: 라이브 .env, scratchpad/ (git 기록·아카이브에 0개 파일).
