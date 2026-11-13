#!/usr/bin/env bash
# 변이마다 던져버릴 worktree에서 코드를 한 줄 깨뜨리고 시험이 실패하는지, 원복 뒤 통과하는지 CAUGHT / NOT_CAUGHT로 출력한다.
# 사용: bash reproduce.sh [REPO_DIR] [PYTHON] [변이 id ...]   (키·DB·네트워크·서버 없음. REPO_DIR의 파일은 건드리지 않는다)
# 환경 변수: COMMIT=검사할 커밋(기본 HEAD), OUT=출력 폴더(기본 ./reproduced)
# CAUGHT = 변이 시 시험 실패 + 원복 뒤 통과 + worktree 깨끗. NOT_CAUGHT = 깨뜨린 코드로도 시험 통과(그 가드는 시험되지 않음).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${1:-.}"; PY="${2:-python}"; COMMIT="${COMMIT:-HEAD}"
WT="$(mktemp -d)/wt"; OUT="${OUT:-$PWD/reproduced}"; mkdir -p "$OUT"
git -C "$REPO" worktree add --detach "$WT" "$COMMIT" >/dev/null
trap 'git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1 || true' EXIT
python3 "$HERE/driver.py" "$WT" "$HERE/mutation_spec.json" "$OUT" "$PY" "${@:3}"
python3 "$HERE/threshold_demo.py" "$WT" "$OUT" "$PY" >/dev/null && echo "threshold demo written to $OUT/threshold_{pass,fail}.txt"
test -z "$(git -C "$WT" status --porcelain)" && echo "worktree clean at end"
