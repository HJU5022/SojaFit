#!/bin/sh
# D12 (2026-11-17) cold-boot loop: one fresh docker:dind per run (empty engine), boot.py prep + cold.
# After run 1 only: full pytest in the built API image (side venv) and the CI replay check (record_demo.py replay, fresh -p project).
# No new run starts after STOP_AT (KST HHMM). Usage: sh loop.sh <N> <STOP_AT>
set -u
HERE=$(cd "$(dirname "$0")" && pwd); OUTROOT=$(dirname "$HERE")
N=${1:-6}; STOP_AT=${2:-0610}; D=sojafit-boot-d12
i=1
while [ "$i" -le "$N" ]; do
  now=$(TZ=Asia/Seoul date +%H%M)
  if [ "$now" -ge "$STOP_AT" ]; then echo "stop: $now >= $STOP_AT before run $i"; break; fi
  docker rm -f -v "$D" >/dev/null 2>&1
  docker run -d --privileged --name "$D" -e DOCKER_TLS_CERTDIR= docker:dind >/dev/null
  until docker exec "$D" docker info >/dev/null 2>&1; do sleep 1; done
  docker image inspect docker:dind --format '{{.Id}} {{index .RepoDigests 0}}' > "$OUTROOT/dind_image.txt"
  export BOOT_OUT="$OUTROOT/run$i" DIND="$D"
  python3 "$HERE/boot.py" prep
  docker cp "$HERE/login.py" "$D:/tools/login.py"
  python3 "$HERE/boot.py" cold
  if [ "$i" -eq 1 ]; then
    X="$OUTROOT/../checks"; mkdir -p "$X"
    IMG=$(docker exec "$D" docker images --format '{{.Repository}}' | grep -E 'api$' | head -1)
    {
      echo "# pytest full run log (Linux container, d12)"; echo "date: $(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M KST')"
      echo "commit: $(docker exec "$D" git -C /work/proj3-b rev-parse HEAD) (GitHub main clone + checkout, local re-clone /work/pt)"
      echo "image: $IMG (built by docker compose up --build in run1 of the cold-boot loop), id $(docker exec "$D" docker image inspect "$IMG" --format '{{.Id}}')"
      echo "command: docker run --rm --user root -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e UV_LINK_MODE=copy -e PYTHONDONTWRITEBYTECODE=1 -v /work/pt:/work -w /work $IMG sh -c 'apt-get install git; uv run --locked pytest -p no:cacheprovider -rs'"
      echo "------------------------------------------------------------"
      docker exec "$D" sh -c "rm -rf /work/pt && git clone -q /work/proj3-b /work/pt && docker run --rm --user root -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e UV_LINK_MODE=copy -e PYTHONDONTWRITEBYTECODE=1 -v /work/pt:/work -w /work $IMG sh -c 'uname -m; python3 --version; apt-get update -qq >/dev/null && apt-get install -y -qq git >/dev/null 2>&1; git --version; git config --global --add safe.directory /work; uv run --locked pytest -p no:cacheprovider -rs'" 2>&1
      echo "exit: $?"
    } > "$X/pytest_full_linux.txt"
    {
      echo "# CI eval-replay (.github/workflows/ci.yml) inside the run1 dind, d12"; echo "date: $(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M KST')"
      echo "commit: $(docker exec "$D" git -C /work/proj3-b rev-parse HEAD)"
      echo "------------------------------------------------------------"
      docker exec -w /work/proj3-b "$D" sh -c 'docker compose -p sojafit-ci run --rm -e DEMO_MODE=1 -e OPENROUTER_API_KEY= -e VOYAGE_API_KEY= -v "$PWD/scripts:/app/scripts:ro" -v "$PWD/evals:/app/evals:ro" -v "$PWD/data/demo:/app/data/demo:ro" api python scripts/demo/record_demo.py replay' 2>&1
      echo "exit: $?"
      docker exec -w /work/proj3-b "$D" docker compose -p sojafit-ci down -v >/dev/null 2>&1
    } > "$X/replay_check.txt"
  fi
  docker rm -f -v "$D" >/dev/null 2>&1
  i=$((i + 1))
done
echo "loop done: $(TZ=Asia/Seoul date)"
