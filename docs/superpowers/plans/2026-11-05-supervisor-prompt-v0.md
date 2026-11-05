# Supervisor Prompt V0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SojaFit Supervisor Prompt V0의 공통 의미 계약을 구현하고 `openai/gpt-6-luna`, `anthropic/claude-haiku-5.5`, `typesafe/jev-1.14`를 같은 상태 라우팅 평가셋으로 비교할 수 있게 한다.

**Architecture:** `backend/graph/supervisor.py`가 질문 유형, 근거, 행동, 사유 코드와 상태 기반 라우팅 검증의 정본이다. Luna와 Haiku는 `backend/prompts/supervisor_v0.md`를 Chat Completions 구조화 출력으로 사용하고, Jev는 같은 의미 계약에서 만든 typed questions를 Decisions API에 사용한다. 두 API의 직렬화 방식은 다르지만 입력 상태, 허용값, 분류 정의, 근거 의미와 라우팅 규칙은 공유한다.

**Tech Stack:** Python 3.12, Pydantic 2, pytest 8, OpenRouter Chat Completions, OpenRouter Decisions API, uv

## Global Constraints

- 작업 브랜치는 `docs/supervisor-luna-selection`이며 `main`에서 직접 작업하지 않는다.
- `uv`로 실행하고 새 의존성을 추가하지 않는다.
- LLM 호출은 `backend/services/llm.py` 경계를 유지한다.
- 숫자·단위 비교와 대체 판정은 Supervisor가 수행하지 않는다.
- 출력 계약은 `question_type`, `required_evidence`, `next_action`, `reason_code` 네 필드만 사용한다.
- 후보는 `openai/gpt-6-luna`, `anthropic/claude-haiku-5.5`, `typesafe/jev-1.14` 세 모델로 고정한다.
- 기존 `evals/dataset_v2.jsonl`과 `evals/FROZEN.json`은 수정하지 않는다.
- 기존 70문항은 `question_type` 기준선에만 사용하고, 다른 필드의 정확도를 gold 없이 만들지 않는다.
- prompt injection 방어는 이번 구현 범위에서 제외하고 입력 경계만 유지한다.
- provider fallback을 사용하지 않는다.
- 라이브 API 호출은 구현·오프라인 테스트와 분리하고 사용자의 별도 비용 승인을 받은 뒤 실행한다.
- 현재 untracked인 `evals/runners/run_supervisor_models.py`, `evals/runners/run_supervisor_jev.py`와 대응 테스트는 참고용으로만 읽고 수정·스테이징·커밋하지 않는다.
- 이 저장소의 로컬 `commit.gpgsign=false` 설정을 유지한다.

---

## File Map

- Create: `backend/graph/supervisor.py` — 공통 스키마, 입력 envelope, 의미 검증, Jev typed-question 생성
- Create: `backend/prompts/supervisor_v0.md` — Luna·Haiku용 명시적 규칙형 시스템 프롬프트
- Modify: `backend/prompts/PROMPTS.md` — V0 프롬프트 버전과 파일 설명
- Create: `tests/graph/test_graph_supervisor.py` — 공통 계약과 프롬프트의 오프라인 단위 테스트
- Create: `evals/samples/supervisor_prompt_v0.jsonl` — 상태 전이 gold가 있는 별도 평가셋
- Create: `evals/samples/supervisor_prompt_v0_frozen.json` — 평가셋 SHA-256과 건수
- Create: `evals/runners/supervisor_prompt_v0_common.py` — 평가셋 로딩, gold 제거, 채점과 통합 요약
- Create: `tests/evals/test_supervisor_prompt_v0_common.py` — 동결·누출·채점 테스트
- Create: `evals/runners/run_supervisor_prompt_v0.py` — Luna·Haiku 전용 V0 plan/smoke/run 진입점
- Create: `tests/evals/test_supervisor_prompt_v0.py` — Chat Completions V0 실행기의 오프라인 테스트
- Create: `evals/runners/run_supervisor_prompt_v0_jev.py` — Jev 전용 V0 plan/smoke/run 진입점
- Create: `tests/evals/test_supervisor_prompt_v0_jev.py` — Jev V0 계약·의미 검증 테스트
- Create: `evals/runners/compare_supervisor_prompt_v0.py` — 세 모델 결과 통합 검증·집계
- Create: `tests/evals/test_compare_supervisor_prompt_v0.py` — 통합 집계 테스트
- Modify: `backend/graph/GRAPH.md` — Supervisor V0의 구현 범위와 미연결 상태
- Create: `evals/runners/SUPERVISOR_PROMPT_V0.md` — V0 실행 순서와 라이브 승인 경계

---

### Task 1: 공통 Supervisor 계약과 프롬프트

**Files:**
- Create: `backend/graph/supervisor.py`
- Create: `backend/prompts/supervisor_v0.md`
- Modify: `backend/prompts/PROMPTS.md`
- Create: `tests/graph/test_graph_supervisor.py`

**Interfaces:**
- Consumes: 사용자 요청 문자열, 현재 상태 dict, 외부 자료 list
- Produces: `SupervisorDecision`, `build_input_envelope(user_request, current_state, external_material) -> dict`, `render_chat_input(envelope) -> str`, `semantic_errors(decision, state) -> list[str]`, `build_jev_question_contract() -> dict`

- [ ] **Step 1: 공통 계약의 실패 테스트 작성**

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.graph.supervisor import (
    SupervisorDecision,
    build_input_envelope,
    build_jev_question_contract,
    render_chat_input,
    semantic_errors,
)


def test_decision_forbids_extra_fields_and_unknown_values():
    with pytest.raises(ValidationError):
        SupervisorDecision.model_validate({
            "question_type": "candidate_judge",
            "required_evidence": ["circuit", "datasheet"],
            "next_action": "search_agent",
            "reason_code": "CANDIDATE_JUDGE",
            "answer": "수퍼바이저가 답을 만들면 안 됨",
        })


def test_input_envelope_keeps_three_boundaries_and_no_gold():
    envelope = build_input_envelope(
        "D3 대신 1N60P를 쓸 수 있나?",
        current_state={"available_evidence": ["circuit"]},
        external_material=[{"source": "datasheet", "text": "VF table"}],
    )
    assert set(envelope) == {"user_request", "current_state", "external_material"}
    assert "gold" not in render_chat_input(envelope)


def test_semantic_validation_checks_reason_order_and_next_action():
    decision = SupervisorDecision(
        question_type="candidate_judge",
        required_evidence=["datasheet", "circuit"],
        next_action="judge_answer_agent",
        reason_code="RATING",
    )
    errors = semantic_errors(decision, {"available_evidence": ["circuit"]})
    assert errors == ["evidence_order", "reason_code", "next_action"]


def test_jev_contract_uses_same_six_types_and_four_actions():
    contract = build_jev_question_contract()
    assert set(contract["question_type"]["criteria"]) == {
        "out_of_scope", "insufficient_information", "candidate_judge",
        "candidate_find", "role", "rating",
    }
    assert set(contract["next_action"]["criteria"]) == {
        "circuit_agent", "search_agent", "judge_answer_agent", "refuse",
    }


def test_prompt_has_v0_rules_and_no_injection_defense_yet():
    prompt = Path("backend/prompts/supervisor_v0.md").read_text(encoding="utf-8")
    for token in ("candidate_judge", "required_evidence", "judge_answer_agent", "INSUFFICIENT_INFORMATION"):
        assert token in prompt
    assert "ignore previous instructions" not in prompt.lower()
```

- [ ] **Step 2: 실패 확인**

Run: `uv run --no-sync pytest tests/graph/test_graph_supervisor.py -q`

Expected: FAIL because `backend.graph.supervisor` and `backend/prompts/supervisor_v0.md` do not exist.

- [ ] **Step 3: 공통 계약 최소 구현**

Create `backend/graph/supervisor.py` with these public definitions:

```python
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

QuestionType = Literal[
    "out_of_scope", "insufficient_information", "candidate_judge",
    "candidate_find", "role", "rating",
]
EvidenceType = Literal["circuit", "datasheet", "approved_case"]
NextAction = Literal["circuit_agent", "search_agent", "judge_answer_agent", "refuse"]
ReasonCode = Literal[
    "OUT_OF_SCOPE", "INSUFFICIENT_INFORMATION", "CANDIDATE_JUDGE",
    "CANDIDATE_FIND", "ROLE", "RATING",
]

EVIDENCE_ORDER = ("circuit", "datasheet", "approved_case")
REASON_BY_TYPE = {
    "out_of_scope": "OUT_OF_SCOPE",
    "insufficient_information": "INSUFFICIENT_INFORMATION",
    "candidate_judge": "CANDIDATE_JUDGE",
    "candidate_find": "CANDIDATE_FIND",
    "role": "ROLE",
    "rating": "RATING",
}


class SupervisorDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: QuestionType
    required_evidence: list[EvidenceType]
    next_action: NextAction
    reason_code: ReasonCode


def build_input_envelope(user_request: str, *, current_state: dict | None = None,
                         external_material: list | None = None) -> dict:
    return {
        "user_request": user_request,
        "current_state": current_state or {
            "completed_actions": [], "available_evidence": [],
            "last_result": None, "failures": [],
        },
        "external_material": external_material or [],
    }


def render_chat_input(envelope: dict) -> str:
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True)


def _expected_action(decision: SupervisorDecision, state: dict) -> str:
    if decision.question_type in {"out_of_scope", "insufficient_information"}:
        return "refuse"
    if state.get("retry_exhausted"):
        return "refuse"
    if decision.question_type == "role":
        return "circuit_agent"
    available = set(state.get("available_evidence", []))
    missing = [item for item in decision.required_evidence if item not in available]
    if "circuit" in missing:
        return "circuit_agent"
    if missing:
        return "search_agent"
    return "judge_answer_agent"


def semantic_errors(decision: SupervisorDecision, state: dict) -> list[str]:
    errors = []
    ordered = [item for item in EVIDENCE_ORDER if item in decision.required_evidence]
    if decision.required_evidence != ordered:
        errors.append("evidence_order")
    if decision.reason_code != REASON_BY_TYPE[decision.question_type]:
        errors.append("reason_code")
    if decision.next_action != _expected_action(decision, state):
        errors.append("next_action")
    return errors
```

Add `build_jev_question_contract()` in the same file. It must return the five typed questions `question_type`, `needs_circuit`, `needs_datasheet`, `needs_approved_case`, `next_action`. Copy the six definitions, evidence meaning and routing order from the approved design; do not import or read the Markdown prompt to construct runtime behavior.

- [ ] **Step 4: 명시적 규칙형 프롬프트 작성**

Create `backend/prompts/supervisor_v0.md` with this exact section order:

```markdown
# 역할
너는 SojaFit의 Supervisor다. 사용자 답변을 직접 만들지 않고 현재 상태에서 다음 실행 경로 하나만 결정한다.

# 금지
- 검색, 회로 분석, 수치·단위 비교와 대체 판정을 직접 수행하지 않는다.
- 입력과 현재 상태에 없는 품번, 수치, 극성, 조건과 근거를 추측하지 않는다.
- 네 출력 필드 외의 설명이나 사용자용 답변을 생성하지 않는다.

# 질문 유형
1. out_of_scope: 요청 전체가 다이오드 교체·회로 역할·정격 확인 범위 밖이다.
2. insufficient_information: 범위 안이지만 대상이나 질문 목적이 없어 안전한 다음 작업을 정할 수 없다.
3. candidate_judge: 특정 후보 품번을 대상 위치에 사용할 수 있는지 묻는다.
4. candidate_find: 대체 후보를 요청하지만 후보 품번은 없다.
5. role: 대상 다이오드의 회로 역할·연결·전류 경로를 묻는다.
6. rating: 특정 다이오드의 정격·특성·시험 조건·패키지·개정판을 묻는다.

위 순서대로 처음 만족하는 유형을 고른다. 교체 의도와 단순 사양 질문이 함께 있으면 candidate_judge 또는 candidate_find를 우선한다.

# 필요한 전체 근거
- out_of_scope, insufficient_information: []
- role: [circuit]
- rating: [datasheet]
- candidate_find, candidate_judge: [circuit, datasheet]
- 사용자가 과거 승인 사례를 요구하거나 그 사례의 재사용이 필요할 때만 approved_case를 추가한다.
- 배열 순서는 circuit, datasheet, approved_case다.

# 다음 실행 경로
- out_of_scope 또는 insufficient_information이면 refuse다.
- 현재 상태가 retry_exhausted이면 refuse다.
- role이면 circuit_agent다.
- 필요한 circuit 근거가 없으면 circuit_agent다.
- 필요한 datasheet 또는 approved_case 근거가 없으면 search_agent다.
- 필요한 근거가 모두 있으면 judge_answer_agent다.

# reason_code
question_type을 대문자로 바꾼 고정 대응값만 사용한다.

# 출력
question_type, required_evidence, next_action, reason_code 네 필드만 구조화 출력한다.
```

- [ ] **Step 5: 프롬프트 목록 문서 갱신**

Add one row at the top of `backend/prompts/PROMPTS.md` version table for `supervisor_v0.md`, version `v0`, reason `세 후보의 상태 기반 라우팅 비교 기준선`, evaluation result `오프라인 계약 테스트만; 라이브 미실행`. Add the file to the `## 파일` list.

- [ ] **Step 6: Task 1 테스트와 diff 검사**

Run: `uv run --no-sync pytest tests/graph/test_graph_supervisor.py -q`

Expected: PASS.

Run: `git diff --check -- backend/graph/supervisor.py backend/prompts/supervisor_v0.md backend/prompts/PROMPTS.md tests/graph/test_graph_supervisor.py`

Expected: no output.

- [ ] **Step 7: Task 1 로컬 커밋**

```powershell
git add backend/graph/supervisor.py backend/prompts/supervisor_v0.md backend/prompts/PROMPTS.md tests/graph/test_graph_supervisor.py
git commit -m "feat: add supervisor prompt v0 contract"
```

---

### Task 2: 상태 라우팅 평가셋과 공통 채점

**Files:**
- Create: `evals/samples/supervisor_prompt_v0.jsonl`
- Create: `evals/samples/supervisor_prompt_v0_frozen.json`
- Create: `evals/runners/supervisor_prompt_v0_common.py`
- Create: `tests/evals/test_supervisor_prompt_v0_common.py`

**Interfaces:**
- Consumes: JSONL rows with `id`, `user_request`, `current_state`, `external_material`, `gold`
- Produces: `load_v0_dataset(dataset, frozen) -> list[dict]`, `model_input(item) -> dict`, `score_decisions(rows, items) -> dict`

- [ ] **Step 1: 동결·gold 누출·채점 실패 테스트 작성**

```python
import json

import pytest

from evals.runners.supervisor_prompt_v0_common import (
    load_v0_dataset,
    model_input,
    score_decisions,
)


def test_loader_checks_count_and_hash(tmp_path):
    dataset = tmp_path / "v0.jsonl"
    dataset.write_text('{"id":"x"}\n', encoding="utf-8")
    frozen = tmp_path / "frozen.json"
    frozen.write_text(json.dumps({"sha256": "0" * 64, "count": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        load_v0_dataset(dataset, frozen)


def test_model_input_never_contains_gold():
    item = {
        "id": "sv0-01", "user_request": "D1 역할은?",
        "current_state": {}, "external_material": [],
        "gold": {"question_type": "role"},
    }
    encoded = json.dumps(model_input(item), ensure_ascii=False)
    assert "gold" not in encoded and "role" not in encoded


def test_score_separates_schema_semantics_and_exact_fields():
    items = [{"id": "sv0-01", "gold": {
        "question_type": "rating", "required_evidence": ["datasheet"],
        "next_action": "search_agent", "reason_code": "RATING",
    }}]
    rows = [{"case_id": "sv0-01", "status": "complete", "semantic_errors": [],
             "decision": items[0]["gold"]}]
    summary = score_decisions(rows, items)
    assert summary["question_type_accuracy"] == 1.0
    assert summary["required_evidence_exact_match"] == 1.0
    assert summary["next_action_accuracy"] == 1.0
    assert summary["semantic_valid_rate"] == 1.0
```

- [ ] **Step 2: 실패 확인**

Run: `uv run --no-sync pytest tests/evals/test_supervisor_prompt_v0_common.py -q`

Expected: FAIL because the common module and dataset do not exist.

- [ ] **Step 3: 정확히 13개 상태 평가 행 작성**

Create `evals/samples/supervisor_prompt_v0.jsonl` with one JSON object per line. Use these IDs and gold decisions:

```text
sv0-01 MOSFET 추천 요청 → out_of_scope, [], refuse, OUT_OF_SCOPE
sv0-02 "대체 가능한지 봐줘"처럼 대상·후보 없음 → insufficient_information, [], refuse, INSUFFICIENT_INFORMATION
sv0-03 D1 역할 질문 → role, [circuit], circuit_agent, ROLE
sv0-04 1N5817 정격 질문, 근거 없음 → rating, [datasheet], search_agent, RATING
sv0-05 대체 후보 검색, 근거 없음 → candidate_find, [circuit,datasheet], circuit_agent, CANDIDATE_FIND
sv0-06 sv0-05와 같은 요청, circuit 확보 → candidate_find, [circuit,datasheet], search_agent, CANDIDATE_FIND
sv0-07 sv0-05와 같은 요청, circuit·datasheet 확보 → candidate_find, [circuit,datasheet], judge_answer_agent, CANDIDATE_FIND
sv0-08 특정 후보 대체 질문, 근거 없음 → candidate_judge, [circuit,datasheet], circuit_agent, CANDIDATE_JUDGE
sv0-09 sv0-08과 같은 요청, circuit 확보 → candidate_judge, [circuit,datasheet], search_agent, CANDIDATE_JUDGE
sv0-10 sv0-08과 같은 요청, circuit·datasheet 확보 → candidate_judge, [circuit,datasheet], judge_answer_agent, CANDIDATE_JUDGE
sv0-11 승인 사례도 요구, circuit·datasheet 확보 → candidate_judge, [circuit,datasheet,approved_case], search_agent, CANDIDATE_JUDGE
sv0-12 sv0-11과 같은 요청, 세 근거 확보 → candidate_judge, [circuit,datasheet,approved_case], judge_answer_agent, CANDIDATE_JUDGE
sv0-13 대체 질문, circuit 확보, search_agent retry_exhausted → candidate_judge, [circuit,datasheet], refuse, CANDIDATE_JUDGE
```

For paired rows, keep `user_request` byte-identical and change only `current_state`. Use `available_evidence` in the fixed order and represent terminal search failure as `"retry_exhausted": true`. `external_material` may contain short synthetic labels such as `{"source":"circuit","ref":"fixture-circuit"}`; do not copy production documents.

- [ ] **Step 4: 동결 metadata 생성**

Run:

```powershell
(Get-FileHash evals/samples/supervisor_prompt_v0.jsonl -Algorithm SHA256).Hash.ToLower()
(Get-Content evals/samples/supervisor_prompt_v0.jsonl).Count
```

Expected: count is `13`; hash is a 64-character lowercase hex string. Use `apply_patch` to create `evals/samples/supervisor_prompt_v0_frozen.json`; set `sha256` to the exact first command output and `count` to the exact second command output. Re-run `Get-FileHash` after the patch and assert the stored value matches; never estimate the hash.

- [ ] **Step 5: 공통 loader와 scorer 최소 구현**

Implement the loader and input boundary as follows, then calculate field metrics over all gold rows; a failed or missing row contributes zero rather than disappearing from a denominator:

```python
def load_v0_dataset(dataset: Path, frozen: Path) -> list[dict]:
    raw = Path(dataset).read_bytes()
    metadata = json.loads(Path(frozen).read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
        raise ValueError("supervisor V0 dataset hash 불일치")
    items = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(items) != metadata["count"] or len({item["id"] for item in items}) != len(items):
        raise ValueError("supervisor V0 dataset count/id 불일치")
    return items


def model_input(item: dict) -> dict:
    return build_input_envelope(
        item["user_request"],
        current_state=item["current_state"],
        external_material=item["external_material"],
    )


def score_decisions(rows: list[dict], items: list[dict]) -> dict:
    by_id = {row["case_id"]: row for row in rows}
    total = len(items)

    def rate(predicate):
        return sum(predicate(by_id.get(item["id"]), item["gold"]) for item in items) / total

    complete = lambda row: bool(row and row.get("status") == "complete")
    return {
        "question_type_accuracy": rate(lambda row, gold: complete(row) and row["decision"]["question_type"] == gold["question_type"]),
        "required_evidence_exact_match": rate(lambda row, gold: complete(row) and row["decision"]["required_evidence"] == gold["required_evidence"]),
        "next_action_accuracy": rate(lambda row, gold: complete(row) and row["decision"]["next_action"] == gold["next_action"]),
        "reason_code_accuracy": rate(lambda row, gold: complete(row) and row["decision"]["reason_code"] == gold["reason_code"]),
        "semantic_valid_rate": rate(lambda row, gold: complete(row) and not row.get("semantic_errors")),
        "exact_decision_match": rate(lambda row, gold: complete(row) and row["decision"] == gold),
    }
```

`model_input()` must call `build_input_envelope()` and must never include `id` or `gold`. `score_decisions()` must use all 13 gold rows as denominators and report completion separately; failed rows do not disappear from the denominator.

- [ ] **Step 6: Task 2 테스트와 diff 검사**

Run: `uv run --no-sync pytest tests/evals/test_supervisor_prompt_v0_common.py -q`

Expected: PASS.

Run: `git diff --check -- evals/samples/supervisor_prompt_v0.jsonl evals/samples/supervisor_prompt_v0_frozen.json evals/runners/supervisor_prompt_v0_common.py tests/evals/test_supervisor_prompt_v0_common.py`

Expected: no output.

- [ ] **Step 7: Task 2 로컬 커밋**

```powershell
git add evals/samples/supervisor_prompt_v0.jsonl evals/samples/supervisor_prompt_v0_frozen.json evals/runners/supervisor_prompt_v0_common.py tests/evals/test_supervisor_prompt_v0_common.py
git commit -m "test: add supervisor v0 routing dataset"
```

---

### Task 3: Luna·Haiku Chat Completions V0 실행 경로

**Files:**
- Create: `evals/runners/run_supervisor_prompt_v0.py`
- Create: `tests/evals/test_supervisor_prompt_v0.py`

**Interfaces:**
- Consumes: Task 1 `SupervisorDecision`, prompt file and Task 2 dataset
- Produces: offline `plan`, explicit `smoke`, explicit `run` for Luna and Haiku

- [ ] **Step 1: 기존 untracked 파일을 수정하지 않는지 확인**

Run:

```powershell
git status --short -- evals/runners/run_supervisor_models.py tests/evals/test_supervisor_models.py
```

Expected: current status is recorded before implementation. The two paths must have identical status and content after Task 3.

- [ ] **Step 2: V0 Chat runner 실패 테스트 작성**

Create `tests/evals/test_supervisor_prompt_v0.py`:

```python
import json

import pytest

from evals.runners import run_supervisor_prompt_v0 as runner


def test_v0_chat_models_are_exactly_luna_and_haiku():
    assert runner.MODELS == ("openai/gpt-6-luna", "anthropic/claude-haiku-5.5")


def test_v0_job_sends_envelope_without_gold():
    calls = []
    item = {
        "id": "sv0-01", "user_request": "MOSFET 추천해 줘",
        "current_state": {}, "external_material": [],
        "gold": {"question_type": "out_of_scope"},
    }

    def fake_call(model, system, user, schema, **kwargs):
        calls.append((model, system, user, schema))
        assert "gold" not in user
        return schema(
            question_type="out_of_scope", required_evidence=[],
            next_action="refuse", reason_code="OUT_OF_SCOPE",
        ), {"usage": {"total_tokens": 1}}

    row = runner.run_one("openai/gpt-6-luna", item, call=fake_call)
    assert row["status"] == "complete"
    assert row["semantic_errors"] == []


def test_plan_is_network_free_and_contains_26_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.llm, "_evaluation_client",
                        lambda timeout: pytest.fail("plan must not create client"))
    output = tmp_path / "chat-v0"
    assert runner.main(["plan", str(output)]) == 0
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["jobs"]) == 26


def test_live_commands_require_confirmation_and_positive_budget(tmp_path):
    with pytest.raises(SystemExit):
        runner.main(["run", str(tmp_path), "--model", "openai/gpt-6-luna", "--max-usd", "1"])
    with pytest.raises(SystemExit):
        runner.main(["run", str(tmp_path), "--model", "openai/gpt-6-luna",
                     "--max-usd", "0", "--confirm-live"])
```

- [ ] **Step 3: 실패 확인**

Run: `uv run --no-sync pytest tests/evals/test_supervisor_prompt_v0.py -q`

Expected: FAIL because the V0 runner does not exist.

- [ ] **Step 4: 독립 V0 Chat runner 구현**

Create `evals/runners/run_supervisor_prompt_v0.py` with these fixed constants and public functions:

```python
MODELS = ("openai/gpt-6-luna", "anthropic/claude-haiku-5.5")
PROVIDER_POLICY = {
    "zdr": True, "data_collection": "deny",
    "allow_fallbacks": False, "require_parameters": True,
}
PROMPT = (ROOT / "backend/prompts/supervisor_v0.md").read_text(encoding="utf-8")


def build_plan(items: list[dict]) -> list[dict]:
    return [
        {"model_id": model, "case_id": item["id"], "run_index": 1}
        for model in MODELS for item in items
    ]
```

Add the exact public signatures `create_manifest(dataset=DATASET, frozen=FROZEN) -> dict`, `run_one(model: str, item: dict, *, call=llm.evaluation_chat, clock=time.perf_counter) -> dict`, `execute_model(run_dir: Path, model: str, *, max_usd: float, max_seconds: float, prompt_rate: float, completion_rate: float, call=llm.evaluation_chat) -> dict`, and `main(argv=None) -> int`.

Build the user message with `render_chat_input(model_input(item))`. `run_one()` retries only `EvaluationFormatError` or Pydantic validation failures, for at most three raw attempts total. It records first-pass validity separately, sanitizes exception messages to `error_type`, validates model ID, and attaches `semantic_errors(decision, item["current_state"])` to complete rows.

`execute_model()` must use `llm.EvaluationBudget` and `llm.evaluation_limits`, save after every case, stop after three consecutive provider errors, and never switch providers. `plan` is network-free. `smoke` and `run` require `--confirm-live`, one exact model, positive `--max-usd`, `--max-seconds`, `--prompt-rate` and `--completion-rate` values. The manifest stores dataset hash, prompt hash, common module hash, exact model IDs, provider policy and 26 jobs.

- [ ] **Step 5: Chat runner 오프라인 회귀 테스트**

Run: `uv run --no-sync pytest tests/evals/test_supervisor_prompt_v0.py tests/evals/test_supervisor_prompt_v0_common.py tests/services/test_llm.py -q`

Expected: PASS with no network calls.

Run: `git diff --check -- evals/runners/run_supervisor_prompt_v0.py tests/evals/test_supervisor_prompt_v0.py`

Expected: no output.

- [ ] **Step 6: 기존 untracked 파일 불변 확인**

Run: `git status --short -- evals/runners/run_supervisor_models.py tests/evals/test_supervisor_models.py`

Expected: Step 1과 동일한 status. `git diff` 또는 파일 hash도 Step 1과 동일해야 한다.

- [ ] **Step 7: Task 3 로컬 커밋**

```powershell
git add evals/runners/run_supervisor_prompt_v0.py tests/evals/test_supervisor_prompt_v0.py
git commit -m "feat: add chat supervisor v0 evaluation"
```

---

### Task 4: Jev Decisions V0 실행 경로

**Files:**
- Create: `evals/runners/run_supervisor_prompt_v0_jev.py`
- Create: `tests/evals/test_supervisor_prompt_v0_jev.py`

**Interfaces:**
- Consumes: Task 1 `build_jev_question_contract`, Task 2 input envelope and dataset
- Produces: Jev plan/smoke/run rows in the same normalized four-field decision shape

- [ ] **Step 1: 공통 의미 계약 사용 실패 테스트 작성**

```python
import json

import pytest

from backend.graph.supervisor import build_jev_question_contract
from evals.runners import run_supervisor_prompt_v0_jev as jev


def jev_response(**choices):
    return {"answers": {
        key: {"type": "choice", "choice": value, "confidence": 1.0,
              "probabilities": {value: 1.0}}
        for key, value in choices.items()
    }}


def item_with_only_circuit():
    return {
        "id": "sv0-09", "user_request": "D3 대신 1N60P를 쓸 수 있나?",
        "current_state": {"available_evidence": ["circuit"]},
        "external_material": [{"source": "circuit", "ref": "fixture-circuit"}],
        "gold": {
            "question_type": "candidate_judge",
            "required_evidence": ["circuit", "datasheet"],
            "next_action": "search_agent", "reason_code": "CANDIDATE_JUDGE",
        },
    }


def test_jev_uses_canonical_v0_contract():
    assert jev.QUESTION_CONTRACT == build_jev_question_contract()


def test_jev_request_uses_same_input_envelope_without_gold():
    item = {
        "id": "sv0-01", "user_request": "MOSFET 추천해 줘",
        "current_state": {}, "external_material": [],
        "gold": {"question_type": "out_of_scope"},
    }
    request = jev.build_request_from_item(item)
    assert request["model"] == "typesafe/jev-1.14"
    assert set(request["state"]) == {"user_request", "current_state", "external_material"}
    assert "gold" not in str(request)


def test_jev_row_records_semantic_errors_separately():
    payload = jev_response(
        question_type="candidate_judge", needs_circuit="yes",
        needs_datasheet="yes", needs_approved_case="no",
        next_action="judge_answer_agent",
    )
    row = jev.parse_item_response(item_with_only_circuit(), payload)
    assert row["semantic_errors"] == ["next_action"]


def test_jev_plan_is_network_free(tmp_path, monkeypatch):
    monkeypatch.setattr(jev.llm, "evaluation_decision",
                        lambda request: pytest.fail("plan must not call Decisions API"))
    output = tmp_path / "jev-v0"
    assert jev.main(["plan", str(output)]) == 0
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["jobs"]) == 13
```

- [ ] **Step 2: 실패 확인**

Run: `uv run --no-sync pytest tests/evals/test_supervisor_prompt_v0_jev.py -q`

Expected: FAIL because the V0 Jev runner does not exist.

- [ ] **Step 3: 독립 V0 Jev runner 구현**

Create `evals/runners/run_supervisor_prompt_v0_jev.py` with fixed `MODEL_ID = "typesafe/jev-1.14"`, `QUESTION_CONTRACT = build_jev_question_contract()`, the same V0 dataset paths, and provider policy `zdr=true`, `data_collection=deny`, `allow_fallbacks=false`.

Keep Decisions-specific confidence and probability validation local to this new runner. Derive `reason_code` with `REASON_BY_TYPE`, preserve evidence order, and call `semantic_errors()` after normalization.

Change the request state from:

```python
{"user_input": user_input}
```

to the exact Task 1 envelope:

```python
model_input(item)
```

The API request uses five typed questions because `typesafe/jev-1.14` is a Decisions model. Add the public signatures `build_request_from_item(item: dict, provider: str | None = None) -> dict`, `parse_item_response(item: dict, payload: dict) -> dict`, `create_manifest(dataset=DATASET, frozen=FROZEN) -> dict`, `execute(run_dir: Path, *, max_calls: int, max_seconds: float, approved_max_usd: float) -> dict`, and `main(argv=None) -> int`.

Record `question_contract_sha256` and the common semantic contract module hash in the manifest. `plan` is network-free; `smoke` and `run` require `--confirm-live`, positive `--max-calls`, `--max-seconds` and `--max-usd` approval values. Enforce call and time caps locally. If Decisions usage does not report an enforceable cost, retain `approved_max_usd` as an approval record and report cost as `Not Reported`; never claim the USD cap was technically enforced. Do not claim literal prompt-byte equality with Chat Completions.

- [ ] **Step 4: Jev runner 오프라인 회귀 테스트**

Run: `uv run --no-sync pytest tests/evals/test_supervisor_prompt_v0_jev.py tests/evals/test_supervisor_prompt_v0_common.py tests/services/test_llm.py -q`

Expected: PASS with no network calls.

Run: `git diff --check -- evals/runners/run_supervisor_prompt_v0_jev.py tests/evals/test_supervisor_prompt_v0_jev.py`

Expected: no output.

- [ ] **Step 5: Task 4 로컬 커밋**

```powershell
git add evals/runners/run_supervisor_prompt_v0_jev.py tests/evals/test_supervisor_prompt_v0_jev.py
git commit -m "feat: align jev with supervisor v0 contract"
```

---

### Task 5: 세 모델 통합 집계와 문서화

**Files:**
- Create: `evals/runners/compare_supervisor_prompt_v0.py`
- Create: `tests/evals/test_compare_supervisor_prompt_v0.py`
- Modify: `backend/graph/GRAPH.md`
- Create: `evals/runners/SUPERVISOR_PROMPT_V0.md`

**Interfaces:**
- Consumes: Luna, Haiku, Jev의 normalized result files
- Produces: 모델별 동일 지표와 API 차이를 표시한 summary JSON

- [ ] **Step 1: 통합 집계 실패 테스트 작성**

```python
import json

import pytest

from evals.runners.compare_supervisor_prompt_v0 import compare


@pytest.fixture
def complete_result_files(tmp_path):
    paths = []
    modes = {
        "openai/gpt-6-luna": "chat_completions",
        "anthropic/claude-haiku-5.5": "chat_completions",
        "typesafe/jev-1.14": "decisions",
    }
    decision = {
        "question_type": "out_of_scope", "required_evidence": [],
        "next_action": "refuse", "reason_code": "OUT_OF_SCOPE",
    }
    for index, (model, mode) in enumerate(modes.items()):
        path = tmp_path / f"result-{index}.json"
        path.write_text(json.dumps({
            "model_id": model, "api_mode": mode,
            "dataset_sha256": "a" * 64, "contract_sha256": "b" * 64,
            "rows": [{"case_id": "sv0-01", "status": "complete",
                      "decision": decision, "semantic_errors": []}],
        }), encoding="utf-8")
        paths.append(path)
    return paths


def test_compare_requires_exact_three_models(tmp_path):
    with pytest.raises(ValueError, match="three models"):
        compare([], tmp_path / "summary.json")


def test_compare_keeps_api_modes_separate(tmp_path, complete_result_files):
    output = tmp_path / "summary.json"
    summary = compare(complete_result_files, output)
    assert set(summary["models"]) == {
        "openai/gpt-6-luna", "anthropic/claude-haiku-5.5", "typesafe/jev-1.14",
    }
    assert summary["models"]["typesafe/jev-1.14"]["api_mode"] == "decisions"
    assert summary["models"]["openai/gpt-6-luna"]["api_mode"] == "chat_completions"
    assert json.loads(output.read_text(encoding="utf-8")) == summary
```

- [ ] **Step 2: 실패 확인**

Run: `uv run --no-sync pytest tests/evals/test_compare_supervisor_prompt_v0.py -q`

Expected: FAIL because the comparison module does not exist.

- [ ] **Step 3: 통합 집계 구현**

The aggregator must reject missing models, duplicate model files, dataset hash mismatches, contract hash mismatches and mixed run counts. Report per model:

```python
{
    "api_mode": "chat_completions | decisions",
    "question_type_accuracy": float,
    "required_evidence_exact_match": float,
    "next_action_accuracy": float,
    "reason_code_accuracy": float,
    "first_pass_schema_valid_rate": float | None,
    "final_schema_valid_rate": float,
    "semantic_valid_rate": float,
    "exact_decision_match": float,
    "latency_p50_seconds": float | None,
    "latency_p95_seconds": float | None,
    "usage": dict,
    "cost": dict,
}
```

For Jev, mark Chat JSON first-pass schema comparability as `None`; do not convert it to zero. Preserve Decisions confidence/probability metrics in a separate `decisions_metadata` section.

- [ ] **Step 4: 문서 갱신**

Document in `backend/graph/GRAPH.md` that V0 implements routing contract and offline evaluation support but is not yet connected to `build_graph()`. Create `evals/runners/SUPERVISOR_PROMPT_V0.md` with this execution order:

```text
1. uv run --no-sync python -m evals.runners.run_supervisor_prompt_v0 plan .tmp/supervisor-v0-chat-plan
2. uv run --no-sync python -m evals.runners.run_supervisor_prompt_v0_jev plan .tmp/supervisor-v0-jev-plan
3. Run offline pytest.
4. Obtain explicit user approval for live budget.
5. Run one-case smoke per exact model/provider.
6. Run the 13-case V0 dataset.
7. Compare only matching dataset and contract hashes.
```

State explicitly that no live call occurred during implementation unless a later execution record proves otherwise. Link the design spec, implementation plan, prompt, dataset and both V0 runners.

- [ ] **Step 5: 전체 오프라인 검증**

Run:

```powershell
uv run --no-sync pytest tests/graph/test_graph_supervisor.py tests/evals/test_supervisor_prompt_v0_common.py tests/evals/test_supervisor_prompt_v0.py tests/evals/test_supervisor_prompt_v0_jev.py tests/evals/test_compare_supervisor_prompt_v0.py -q
```

Expected: all selected tests PASS, no network calls.

Run:

```powershell
uv run --no-sync pytest tests/services/test_llm.py tests/graph/test_graph_build.py -q
```

Expected: all adjacent regression tests PASS or pre-existing skips remain skips.

Run: `git diff --check`

Expected: no new whitespace errors. Existing unrelated dirty files remain unmodified by this plan unless named in the File Map.

- [ ] **Step 6: 네트워크 없는 plan smoke**

Run both `plan` commands into new temporary result directories and verify manifests contain only the exact V0 candidates, the 13-case dataset hash and contract hashes. Do not run `smoke` or `run` commands in this task.

- [ ] **Step 7: Task 5 로컬 커밋**

```powershell
git add evals/runners/compare_supervisor_prompt_v0.py tests/evals/test_compare_supervisor_prompt_v0.py backend/graph/GRAPH.md evals/runners/SUPERVISOR_PROMPT_V0.md
git commit -m "docs: add supervisor v0 evaluation workflow"
```

---

## Live Evaluation Gate

Implementation completion does not authorize paid or external model calls. Before live execution, report:

- exact three model IDs and providers
- dataset and contract SHA-256 values
- calls per model, retry maximum and total worst-case raw calls
- per-model and total USD caps
- data retention, ZDR and fallback policy
- one-case smoke command and stop conditions

Proceed only after explicit user approval for that live run. Store results in a new timestamped directory; do not overwrite earlier evaluation artifacts.
