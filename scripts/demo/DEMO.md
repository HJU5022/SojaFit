# demo

## 역할
- 이 폴더: 키 없는 데모가 재생할 LLM 응답을 실제 키로 한 번 기록하고, 키 없이 재생해 결과가 같은지 확인하는 스크립트를 둡니다. 키 없는 compose의 DB(데모 코퍼스 스냅샷)에서 compose 네트워크 안으로 실행합니다. 서비스(`DEMO_REPLAY=1`)는 이 기록을 React 작업대의 분석에서 재생합니다(`backend/conversations/memory_service.py`, SPEC 7절).
- 넣는 것: 기록 · 재생 확인 스크립트(`record_demo.py`).
- 넣지 않는 것: 기록 · 재생 함수와 서비스의 질문 대조(`backend/services/demo.py`), 기록 파일(`data/demo/recordings/`), 스냅샷 만들기(`backend/rag/pipeline/demo_snapshot.py`), 평가 실행(`evals/runners/`), 테스트(`tests/services/test_demo_replay.py`).
- 담당: 서비스·운영

## 파일

| 파일 | 분류 | 분류 근거 | 설명과 명령 |
|---|---|---|---|
| `DEMO.md` | | | 이 문서 |
| `record_demo.py` | 운영 | `.github/workflows/ci.yml`이 `replay`를 실행하고, `tests/services/test_demo_replay.py`·`backend/services/demo.py`가 기록 형식을 맞춤 | 서비스와 같은 멀티 그래프 조립(MCP 사실 확인·카드 도구·BM25 검색, 메모리 체크포인터, Store 없음)으로 데모 질문 10개를 새 대화의 첫 질문처럼 돌린다. `record`는 실제 LLM 응답을 `data/demo/recordings/calls.jsonl`에, 질문별 결과와 DB 지문을 `outcomes.json`에 남기고(유료), `replay`는 키를 지운 채 기록 응답만으로 다시 돌려 경로·답·판정·거절·인터럽트가 같은지 본다(무료). `DEMO_MODE=1`이 아니거나, 기록인데 `OPENROUTER_API_KEY`가 없거나, `LAB_*`·`LLM_MODEL`이 있거나, DB 문서·청크 수가 스냅샷과 다르면 멈춘다. `record`는 `--confirm-live`가 없으면 예상 호출 수만 찍는다 |

## 데모 질문

질문 목록은 `record_demo.py`의 `QUESTIONS`다. 아래 결과는 `data/demo/recordings/outcomes.json`(기록일 2026-11-12, 코드 `8e769db`)에서 옮겼다.

| id | 회로 · 대상 | 유형 | 출처 | 기록 결과 |
|---|---|---|---|---|
| `v3-01` | ATtiny85 Time Switch · D1 | 판정 + 조건 인터럽트(`v_drop_allowed`를 모름으로 재개) | 동결 v3 그대로 | `ROLE_SUFFICIENT` |
| `demo-ask` | ATtiny85 Time Switch · D1 | 판정 + 조건 인터럽트(`v_drop_allowed`에 `1.5V`를 주고 재개) | 데모 전용(v3-01에서 전압강하 제한 문장을 빼고 1N4004G, 전압강하 시험 조건을 적음) | `ROLE_SUFFICIENT` |
| `v3-03` | ATtiny2313A Thermostat · D5 | 판정(동일품: 주문 코드 L0 → L0G) | 동결 v3 그대로 | `IDENTICAL` |
| `demo-notsuff` | SparkFun Breadboard Power Supply 5V/3.3V · D1 | 판정(불충족: 350mA에 1N4148의 평균 전류 0.15A) | 데모 전용(v3-11 회로 · 조건 모양) | `NOT_SUFFICIENT` |
| `demo-find` | Franzininho DIY · D3 | 후보 찾기(스위칭 다이오드 분류 전체가 스냅샷에 있음) | 데모 전용(v3-11 모양을 데모 회로로 바꿈) | 후보 7개 모두 `ROLE_SUFFICIENT` |
| `demo-rating` | Franzininho DIY · D3 | 정격 확인과 인용(1N4148의 VRRM · IF) | 데모 전용(v3-21 모양) | 답 + 인용 |
| `demo-leak` | Adafruit MOSFET Driver STEMMA · D3 | 정격 확인과 시험 조건(1N4007G의 IR 상한, TJ · 전압) | 데모 전용(v3-16 모양) | 답 + 인용 |
| `v3-36` | Franzininho DIY · D3 | 코퍼스에 없는 품번 거절(LL4148은 있고 LL4149는 없음) | 동결 v3 그대로 | 거절 `part_missing` |
| `v3-30` | Franzininho DIY · D3 | 범위 밖 거절 | 동결 v3 그대로 | 거절 `not_found` |
| `demo-edition` | SparkFun Pro Micro v13 · D2 | 개정판 불일치 거절(스냅샷은 N2212, 요청은 N2112) | 데모 전용(v3-45~50 모양) | 거절 `revision_missing` |

- 기록은 18줄이다(`supervisor` 10 · `judge_read` 5 · `docs_answer` 3) [실측: `calls.jsonl`]. 기록 응답은 질문 10개, 회로 6곳이다.
- 인터럽트는 4개 질문에서 났고(`v3-01` · `demo-ask` · `demo-find` · `demo-notsuff`) 모두 같은 대화의 두 번째 단계로 재개해 끝났다. 재개 값은 `outcomes.json`의 `resume`이고 화면의 "기록한 답으로 계속하기"가 그대로 보낸다. 값을 주고 재개하는 질문은 `demo-ask`뿐이다(나머지는 모름).
- 이 기록 방식은 한 프로세스 안(`InMemorySaver`)에서 질문 → 인터럽트 → 재개를 돌린다. 서비스를 다시 띄운 뒤 재개하는 것은 서비스의 Postgres 체크포인트가 맡는 길이고 이 스크립트는 보지 않는다.
- 견적 승인 경로는 재생에 없다(재생 모드의 `can_approve`는 항상 `False`, `memory_service.py`).
- 한계: 기록에 있는 (회로 · 대상 · 질문 · 사용 조건) 조합과 새 대화의 첫 질문만 재생한다. 그 밖의 입력은 422(데모 질문 목록)이고, 프롬프트나 DB가 기록 때와 달라져 기록에 없는 호출이 나오면 503 `UNAVAILABLE`로 멈춘다.
- React 데모 회로(`backend/projects/repository.py`의 `DEMOS`)의 연결 정보가 기록 질문의 넷리스트 옆 `connections.json`과 같을 때만 서비스가 그 질문을 받는다(`tests/services/test_demo_replay.py`가 열 질문 모두 확인).
- 화면은 `GET /api/demo-questions`가 돌려주는 이 목록을 버튼으로 보이고 글자 그대로 새 대화의 첫 질문으로 보낸다. 화면에 질문 글을 따로 적어 두지 않는다.

## 실행

기록은 `.env`의 `OPENROUTER_API_KEY`만 api 컨테이너에 넘기고, `.env`의 나머지 설정(검색 · 재시도 · Langfuse · Exa 등)은 넘기지 않는다. 키 없는 평가자 환경에는 `.env`가 없으므로, 기록 때 그 설정이 켜져 있으면 프롬프트가 달라져 재생이 멈춘다. 그래서 임시 override 파일로 `env_file`을 비운다(저장소에 파일을 두지 않는다).

```bash
# 0) override: api 컨테이너의 env_file을 비운다. 기록용은 키 하나만 넘긴다(값은 compose가 .env에서 치환하고 화면에 찍지 않는다)
OVR=$(mktemp) && printf 'services:\n  api:\n    env_file: !reset []\n' > "$OVR"
OVR_REC=$(mktemp) && printf 'services:\n  api:\n    env_file: !reset []\n    environment:\n      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY}\n' > "$OVR_REC"
# 1) 예상 호출 수만 보기(LLM · DB 호출 없음)
DEMO_MODE=1 uv run python scripts/demo/record_demo.py record
# 2) 기록(유료). -p로 새 프로젝트(새 볼륨)를 써서 corpus-load가 빈 DB에 스냅샷을 넣는다. DB는 compose 안의 db:5432/app이다
docker compose -f docker-compose.yml -f "$OVR_REC" -p sojafit-rec run --rm -e DEMO_MODE=1 -e EXA_WEB_SEARCH_ENABLED=0 -e EXA_API_KEY= -e VOYAGE_API_KEY= \
    -v "${PWD}/scripts:/app/scripts:ro" -v "${PWD}/evals:/app/evals:ro" -v "${PWD}/data/demo:/app/data/demo" api python scripts/demo/record_demo.py record --confirm-live
# 3) 키 없이 재생 확인. 또 다른 새 프로젝트라 평가자의 새 볼륨과 같은 조건에서 청크 id(DB 지문)까지 대조한다
docker compose -f docker-compose.yml -f "$OVR" -p sojafit-chk run --rm -e DEMO_MODE=1 -e OPENROUTER_API_KEY= -e VOYAGE_API_KEY= \
    -v "${PWD}/scripts:/app/scripts:ro" -v "${PWD}/evals:/app/evals:ro" -v "${PWD}/data/demo:/app/data/demo" api python scripts/demo/record_demo.py replay
# 4) 이 두 프로젝트만 지운다
docker compose -p sojafit-rec down -v && docker compose -p sojafit-chk down -v
```

- 기록 전에 `docker compose -f docker-compose.yml -f "$OVR_REC" -p sojafit-rec config --format json`의 api 환경에서 `DATABASE_URL`의 호스트가 `db`인지(`.env`의 `DATABASE_URL`이 아니라 compose 값이 이기는지) 확인한다. 값은 찍지 않고 호스트와 DB 이름만 본다.

- [주의] DB 지문이 다르다고 기본 프로젝트(`-p` 없이)를 `down -v` 하지 않는다. 기본 볼륨의 계정 · 분석 대화가 지워진다. 기록 · 확인은 위처럼 따로 만든 프로젝트에서만 한다.
- 이미지에는 `scripts/` · `evals/`가 없어 붙여 넣고, 기록 파일이 저장소에 남도록 `data/demo/`를 붙인다.
- 커밋 전에 기록 파일을 검사한다(응답 칸만 쓰지만 사람이 한 번 본다): `docker run --rm -v "$PWD":/repo:ro ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f dir /repo/data/demo/recordings --no-banner --redact --config /repo/.gitleaks.toml`. 기록 줄이 해시 모양 id 때문에 걸리면 경로가 아니라 지문을 `.gitleaksignore`에 한 줄 설명과 함께 등록한다.
- 기록은 늘 `calls.jsonl`을 비우고 처음부터 쓴다. 한 질문이라도 멈추면(인터럽트가 둘, 인터럽트를 보일 질문이 멈추지 않음, 형식 실패) `outcomes.json`을 쓰지 않으니 원인을 고치고 다시 돌린다.
