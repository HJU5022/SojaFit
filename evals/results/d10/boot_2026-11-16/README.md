# 새 clone 키 없는 기동 재측정: `main` `3ce5abdc` (2026-11-16)

G2 증거. 11-13 측정(`../startup_restart_isolation_2026-11-13.md`, `jeongun-2` @ `ad8612e`) 뒤에 `Dockerfile` · `docker-compose.yml` · `db/`와 화면 소스가 바뀌어([GATES](../../../../docs/GATES.md) G2 「확인 못 한 것」) 지금 코드로 다시 쟀다. 대상은 발표 때 평가자가 받을 GitHub `main`이다.

## 결과 [실측]

| 항목 | 값 |
|---|---|
| 코드 | GitHub `main` `3ce5abdcc83f578a7ac7b29e58e894c13313a1ed`(트리 `72aed592…`, PR #142 병합). `.env` 없음 · API 키 없음 |
| 환경 | Apple M2 호스트 Docker 29.7.2 위의 빈 `docker:dind`(29.9.3, `docker@sha256:7bf70dcb…`), 이미지 · 볼륨 0개에서 시작([empty_before.txt](empty_before.txt)) |
| 명령 | README의 `docker compose up --build` 한 줄 |
| clone 시작 → clone 끝 | 12.7초 |
| **clone 시작 → `/health` 200** | **242.8초** (기준 600초) |
| clone 시작 → 스모크 끝 | 251.4초 |
| 스모크 | `scripts/smoke/http_smoke.py --base-url http://localhost:8000 --demo --refusal`: **28 통과 · 0 실패 · 0 건너뜀**([smoke_cold.json](smoke_cold.json), [smoke_cold.log.txt](smoke_cold.log.txt)) |
| 내려받은 양 | 585 MB(dind eth0 수신, `/health` 200 시점) |
| 호스트 부하 | 시작 전 1분 평균 22.3 → 300초 기다린 뒤 10.0에서 시작(같은 시각에 다른 측정이 돌았다). 11-13 측정은 5.62에서 시작했다 |

11-13(`ad8612e`) 냉 기동은 clone 시작 → `/health` 200 243.9초, 스모크 28/28이었다. 이번 값은 그와 거의 같다. 부하가 높았으므로 시간 비교의 근거로는 쓰지 않는다.

## 파일

| 파일 | 내용 |
|---|---|
| `timeline_cold.json` · `timeline_prep.json` | 단계 시각표(호스트 KST 시계, `t_sec`는 clone 시작 기준) |
| `cold_driver.log.txt` | 측정 스크립트 출력 |
| `compose_up_cold.log.txt` | `docker compose up --build` 전체 출력(BuildKit plain) |
| `docker_events_cold.jsonl` | dind 안 `docker events` |
| `smoke_cold.json` · `smoke_cold.log.txt` | 스모크 결과 |
| `empty_before.txt` · `dind_image.txt` | 시작 전 빈 엔진 확인, dind 이미지 다이제스트 |
| `scripts/boot.py` | 11-13 `../boot/scripts/boot.py`의 사본. 바꾼 곳은 브랜치(`main`) · 커밋 확인(`3ce5abdc`) · 컨테이너 이름 3가지뿐 |

## 다시 보는 방법

```bash
docker run -d --privileged --name sojafit-boot-1116 -e DOCKER_TLS_CERTDIR= docker:dind
python3 evals/results/d10/boot_2026-11-16/scripts/boot.py prep
python3 evals/results/d10/boot_2026-11-16/scripts/boot.py cold   # GitHub 토큰은 gh auth token을 docker exec 환경변수로만 넘긴다
docker rm -f -v sojafit-boot-1116
```

## 한계

- 1회(냉)다. 온(캐시 있음) 재기동 · 재시작 뒤 재개(G4) 시험은 이번에 하지 않았다.
- Mac 호스트의 docker-in-docker다. Windows · Linux · Docker Desktop 직접 실행은 이 측정에 없다. 발표 현장의 평가자 환경과는 별개다.
- 측정 뒤 dind 컨테이너와 이미지를 지웠다.
