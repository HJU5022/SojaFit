"""Supervisor Prompt V0 후보 모델이 공유하는 평가 입력과 결정적 채점."""

import hashlib
import json
from pathlib import Path

from backend.graph.supervisor import build_input_envelope


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals" / "samples" / "supervisor_prompt_v0.jsonl"
FROZEN = ROOT / "evals" / "samples" / "supervisor_prompt_v0_frozen.json"

DECISION_FIELDS = (
    "question_type",
    "required_evidence",
    "next_action",
    "reason_code",
)


def load_v0_dataset(dataset_path: Path = DATASET, frozen_path: Path = FROZEN) -> list[dict]:
    """별도 V0 표본이 기록된 hash·건수와 정확히 일치할 때만 읽는다."""

    raw = dataset_path.read_bytes()
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != frozen.get("sha256"):
        raise ValueError("supervisor V0 dataset hash mismatch")

    items = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(items) != frozen.get("count"):
        raise ValueError("supervisor V0 dataset count mismatch")
    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)) or any(not case_id for case_id in ids):
        raise ValueError("supervisor V0 dataset ids must be unique and non-empty")
    return items


def model_input(item: dict) -> dict:
    """평가 정답과 식별자를 제외한 세 경계만 모델 입력으로 만든다."""

    return build_input_envelope(
        item["user_request"],
        current_state=item.get("current_state"),
        external_material=item.get("external_material"),
    )


def score_decisions(rows: list[dict], items: list[dict]) -> dict:
    """오류 행을 제외하지 않고 전체 문항을 분모로 네 필드와 의미 일치를 센다."""

    total = len(items)
    if total == 0:
        raise ValueError("cannot score an empty supervisor V0 dataset")

    gold_by_id = {item["id"]: item["gold"] for item in items}
    counts = {field: 0 for field in DECISION_FIELDS}
    completed = semantic_valid = exact = 0

    for row in rows:
        gold = gold_by_id.get(row.get("case_id"))
        decision = row.get("decision")
        if gold is None or row.get("status") != "complete" or not isinstance(decision, dict):
            continue
        completed += 1
        for field in DECISION_FIELDS:
            counts[field] += decision.get(field) == gold[field]
        semantic_valid += not row.get("semantic_errors", [])
        exact += all(decision.get(field) == gold[field] for field in DECISION_FIELDS)

    return {
        "case_count": total,
        "completion_rate": completed / total,
        "question_type_accuracy": counts["question_type"] / total,
        "required_evidence_exact_match": counts["required_evidence"] / total,
        "next_action_accuracy": counts["next_action"] / total,
        "reason_code_accuracy": counts["reason_code"] / total,
        "semantic_valid_rate": semantic_valid / total,
        "exact_decision_match": exact / total,
    }
