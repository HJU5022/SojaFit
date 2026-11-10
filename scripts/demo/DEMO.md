# demo

## 역할
- 이 폴더: 키 없는 데모가 재생할 LLM 응답을 실제 키로 한 번 기록하고, 키 없이 재생해 결과가 같은지 확인하는 스크립트를 둡니다. 키 없는 compose의 DB(데모 코퍼스 스냅샷)에서 compose 네트워크 안으로 실행합니다. 서비스(`DEMO_REPLAY=1`)는 이 기록을 React 작업대의 분석에서 재생합니다(`backend/conversations/memory_service.py`, SPEC 7절).
- 넣는 것: 기록 · 재생 확인 스크립트(`record_demo.py`).
- 넣지 않는 것: 기록 · 재생 함수와 서비스의 질문 대조(`backend/services/demo.py`), 기록 파일(`data/demo/recordings/`), 스냅샷 만들기(`backend/rag/pipeline/demo_snapshot.py`), 평가 실행(`evals/runners/`), 테스트(`tests/services/test_demo_replay.py`).
- 담당: 서비스·운영

## 파일
- `DEMO.md` — 이 문서
- `record_demo.py` — 서비스와 같은 멀티 그래프 조립(MCP 사실 확인 · 카드 도구 · BM25 검색, 메모리 체크포인터, Store 없음)으로 데모 질문 5개를 새 대화의 첫 질문처럼 돌린다. `record`는 실제 LLM 응답을 `data/demo/recordings/calls.jsonl`에, 질문별 결과와 DB 지문을 `outcomes.json`에 남기고, `replay`는 키를 지운 채 기록 응답만으로 다시 돌려 경로 · 답 · 판정 · 거절 · 인터럽트가 같은지 본다. `DEMO_MODE=1`이 아니거나, 기록인데 `OPENROUTER_API_KEY`가 없거나, `LAB_*` · `LLM_MODEL`이 있거나, DB 문서 · 청크 수가 스냅샷과 다르면 멈춘다. `record`는 `--confirm-live`가 없으면 예상 호출 수만 찍는다

## 데모 질문

| id | 무엇을 보이나 | 회로 · 대상 | 출처 |
|---|---|---|---|
| `v3-01` | 후보 판정과 조건 인터럽트(허용 전압강하를 물으면 모름으로 재개) | ATtiny85 Time Switch · D1 | 동결 v3 그대로 |
| `demo-find` | 후보 찾기(스위칭 다이오드 분류 전체가 스냅샷에 있음) | Franzininho DIY · D3 | 데모 전용(v3-11 모양을 데모 회로로 바꿈) |
| `demo-rating` | 정격 확인과 인용 | SparkFun Breadboard Supply · D1 | 데모 전용(v3-21의 1N5408G → 1N4001G) |
| `v3-36` | 코퍼스에 없는 품번 거절(LL4148은 있고 LL4149는 없음) | Franzininho DIY · D3 | 동결 v3 그대로 |
| `v3-30` | 범위 밖 거절 | Franzininho DIY · D3 | 동결 v3 그대로 |

- React 데모 회로(`backend/projects/repository.py`의 `DEMOS`): ATtiny85 Time Switch = `attiny85_time_switch`(`received-20261030/c01`, 11-10 추가), Franzininho DIY = `franzininho_diy`(`c09`), SparkFun Breadboard Supply = `breadboard_supply`. 서비스는 프로젝트의 연결 정보가 기록 질문의 넷리스트 옆 `connections.json`과 같을 때만 그 질문을 받는다(`tests/services/test_demo_replay.py`가 다섯 질문 모두 확인).
- 화면은 이 표의 질문을 버튼으로 보이고 글자 그대로 새 대화의 첫 질문으로 보낸다. `v3-01`의 조건 질문에는 기록한 재개 값(`outcomes.json`의 `resume`)을 그대로 보낸다.

## 실행

```bash
# 1) 예상 호출 수만 보기(LLM · DB 호출 없음, 키는 .env에서 읽음)
DEMO_MODE=1 uv run python scripts/demo/record_demo.py record
# 2) 기록(유료). .env의 OPENROUTER_API_KEY를 compose가 넘긴다. -p로 새 프로젝트(새 볼륨)를 써서 corpus-load가 빈 DB에 스냅샷을 넣는다
docker compose -p sojafit-rec run --rm -e DEMO_MODE=1 -v "${PWD}/scripts:/app/scripts:ro" -v "${PWD}/evals:/app/evals:ro" \
    -v "${PWD}/data/demo:/app/data/demo" api python scripts/demo/record_demo.py record --confirm-live
# 3) 키 없이 재생 확인. 또 다른 새 프로젝트라 평가자의 새 볼륨과 같은 조건에서 청크 id(DB 지문)까지 대조한다
docker compose -p sojafit-chk run --rm -e DEMO_MODE=1 -e OPENROUTER_API_KEY= -v "${PWD}/scripts:/app/scripts:ro" -v "${PWD}/evals:/app/evals:ro" \
    -v "${PWD}/data/demo:/app/data/demo" api python scripts/demo/record_demo.py replay
# 4) 이 두 프로젝트만 지운다
docker compose -p sojafit-rec down -v && docker compose -p sojafit-chk down -v
```

- [주의] DB 지문이 다르다고 기본 프로젝트(`-p` 없이)를 `down -v` 하지 않는다. 기본 볼륨의 계정 · 분석 대화가 지워진다. 기록 · 확인은 위처럼 따로 만든 프로젝트에서만 한다.
- 이미지에는 `scripts/` · `evals/`가 없어 붙여 넣고, 기록 파일이 저장소에 남도록 `data/demo/`를 붙인다.
- 커밋 전에 `gitleaks dir data/demo/recordings --config .gitleaks.toml`로 기록 파일을 검사한다(응답 칸만 쓰지만 사람이 한 번 본다).
- 기록은 늘 `calls.jsonl`을 비우고 처음부터 쓴다. 한 질문이라도 멈추면(인터럽트가 둘, 인터럽트를 보일 질문이 멈추지 않음, 형식 실패) `outcomes.json`을 쓰지 않으니 원인을 고치고 다시 돌린다.
