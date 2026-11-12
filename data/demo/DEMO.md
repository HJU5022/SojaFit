# demo

## 역할
- 이 폴더: 키 없는 데모(`DEMO_MODE=1` · `DEMO_REPLAY=1`) 자료를 둔다. `snapshot/`은 키 없는 compose가 로컬 DB에 넣는 실제 TSC 데이터시트 청크 일부이며, 검색(`retrieve`·MCP `search_corpus`)이 BM25로 읽는다. `recordings/`는 멀티 에이전트 그래프를 이 스냅샷 DB에서 실제 LLM 키로 돌려 남긴 LLM 응답 기록이며, 키 없는 데모의 분석이 같은 질문을 재생할 때 읽는다(`backend/services/demo.py`, 서비스는 `memory_service`). 재생은 기록한 질문에 같은 답을 내는 것만 보이고 새 질문의 품질은 평가하지 않는다. `DEMO_MODE=1`만 켠 평가·실제 모델 확인은 실제 LLM을 그대로 쓴다.
- 넣는 것: 키 없는 compose가 적재할 데모 코퍼스 스냅샷(`snapshot/`, 전체 v4h 청크에서 규칙대로 뽑은 manifest·청크 줄, 임베딩 없음)과 LLM 응답 기록(`recordings/`: 그래프 노드가 schema로 검증한 응답 칸과 질문별 결과만).
- 넣지 않는 것: 가격표와 Mouser 형식의 가격·재고 응답(데모 모드의 `/api/prices`는 값 없이 `available: false`를 돌려준다, SPEC 7절, ADR 0009), 외부 API 응답 원본(HTTP 본문·헤더·사용량·비용), 키, 원본 PDF(`data/corpus/`), `snapshot/` 밖의 데이터시트 청크·발췌.
- 담당: 서비스·운영

## 파일

| 파일·폴더 | 유형 | 설명 |
|---|---|---|
| `DEMO.md` | 폴더 설명 | 이 문서 |
| `snapshot/` | 데이터 | compose `corpus-load`가 로컬 DB에 넣는 데모 코퍼스 스냅샷. 출처·이용 조건·고른 규칙·sha256·문서·청크 수: [SNAPSHOT.md](snapshot/SNAPSHOT.md) |
| `recordings/` | 데이터 | LLM 응답 기록. [scripts/demo/record_demo.py](../../scripts/demo/record_demo.py) `record`가 만들고 `replay`가 키 없이 대조. 실행 방법: [scripts/demo/DEMO.md](../../scripts/demo/DEMO.md) |
| `recordings/calls.jsonl` | 데이터 | LLM 호출마다 한 줄: `sha256`(노드·system·user·schema 이름을 묶은 해시, 재생의 찾기 키), `node`, `schema`, `response`(파싱한 응답). 키·헤더·모델 이름·비용은 없음 |
| `recordings/outcomes.json` | 데이터 | 기록 날짜(`recorded_at`), 노드별 모델(`models`), DB 지문(`db`: 문서·청크 수와 청크 id·본문 sha256 목록의 해시), 질문별(`questions`) 입력·경로·답·판정·거절 코드·인터럽트와 재개 값 |

- 현재 기록은 데모 질문 5개, 호출 8줄이다 [실측: `calls.jsonl` 8줄, `outcomes.json`의 `questions` 5개].
- 프롬프트에 청크 id가 들어가므로 빈 볼륨에 `corpus-load`로 넣은 DB에서만 맞는다. 같은 대화의 두 번째 질문부터는 이전 입력이 프롬프트에 붙어 기록과 달라지므로 데모 질문은 새 대화의 첫 질문으로만 재생된다.

## 실행·시연
- 새 환경에서 `.env` 없이 `docker compose up --build` 후 `http://localhost:8000/login`을 연다. 비밀번호 없이 "데모 사용자 A로 들어가기" · "데모 사용자 B로 들어가기" 버튼으로 들어간다. A · B는 로컬 데모 전용 일반 사용자이며 평가용으로 제출한 계정과 다르다(비밀번호 로그인 불가). 사용자별 격리는 창 두 개(시크릿 창이나 다른 브라우저, 쿠키가 따로)에서 A와 B로 각각 들어가 확인한다.
- 기존 `.env`가 있으면 `DEMO_MODE=1`과 `DEMO_REPLAY=1`을 모두 명시한다(`DEMO_REPLAY`가 비면 compose는 `DEMO_MODE` 값을 쓴다). 기존 볼륨은 초기화하지 않으며 계정 시드는 빈 DB 첫 기동에서만 실행된다.
- React 작업대(`/app`)에서 데모 회로로 프로젝트를 만들고 기록 질문이 있는 부품(ATtiny85 Time Switch D1 · Franzininho DIY D3 · SparkFun Breadboard Power Supply D1)을 고르면 대화 패널에 데모 질문 버튼이 보인다(`GET /api/demo-questions`). 누르면 새 대화로 기록한 질문 · 사용 조건을 그대로 보내고, 조건 질문(`v3-01`)에는 "기록한 답으로 계속하기"로 기록한 답을 보낸다. 질문 목록은 [scripts/demo/DEMO.md](../../scripts/demo/DEMO.md)의 데모 질문 표.
- 기록한 질문 밖의 입력(다른 회로 · 대상 · 질문 · 조건, 같은 대화의 두 번째 질문, 기록과 다른 재개 답)은 422로 데모 질문 목록을 보여 준다. 기록 파일이 없으면 서버는 뜨고 분석만 503이다. 확인을 통과했는데 기록에 없는 호출이 나오면(DB · 코드가 기록 때와 다름) 실제 LLM으로 넘기지 않고 노드 이름을 담은 503으로 멈춘다. 키가 있어도 재생 모드는 LLM을 부르지 않는다.
