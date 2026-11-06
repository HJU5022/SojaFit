"""평가셋 문항과 그래프 실행 상태를 대조해 답변·거절 5지표를 규칙 기반으로 채점한다.

- 역할: 문항(kind, expected, gold_chunks, question_type)과 그래프 최종 상태(path, answer, docs, passed, check, target_part)를
  대조해 관련 문항은 cited_gold(정답 근거 인용)·wrong_citation(오답 근거)·over_refusal(과잉 거절) 셋 중 하나로,
  비관련 문항은 correct_refusal(올바른 거절)·hallucination_risk(환각 위험) 둘 중 하나로 분류한다.
  n01·n02처럼 relevant + NOT_VERIFIED가 정답인 문항에서 정답 청크를 인용해 조건 부족을 설명한 응답은 과잉 거절로 세지 않는다.
- 하지 않는 일: LLM 호출을 통한 서술 의미 채점.
- 출처: docs/experiments/answer-refusal-scorer.md, evals/guides/dataset-guide.md, EVAL_REPORT.md 2장

실행(저장소 루트에서):
    uv run python -m evals.runners.score_answer <평가셋 jsonl> <실행 결과 json> [채점 결과 json]
"""
import json
import sys
from pathlib import Path

from backend.graph.nodes import NOT_FOUND, citations
from evals.runners.run_retrieval import gold_locations

OUT_OF_SCOPE_PREFIX = "이 질문은 SojaFit 범위 밖입니다"
REL_METRICS = ("cited_gold", "wrong_citation", "over_refusal")
IRR_METRICS = ("correct_refusal", "hallucination_risk")


def load_excluded_ids(exclusions_path: Path | None = None) -> set[str]:
    """evals/exclusions.json에서 제외할 문항 ID 집합을 읽는다. 파일이 없으면 빈 집합."""
    path = exclusions_path or (Path(__file__).resolve().parents[1] / "exclusions.json")
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {row["id"] for row in data.get("excluded", []) if "id" in row}


def _used_and_fake(state: dict, answer: str) -> tuple[list[str], list[str], dict[str, dict]]:
    """답변에서 실제 유효 인용(used), 허위 인용(fake), 통과 청크 사전(id_str -> card)을 구한다."""
    passed = set(state.get("passed") or [])
    docs = state.get("docs") or []
    cards = {str(d["chunk_id"]): d for d in docs if d.get("chunk_id") in passed}
    valid = set(cards) | ({"넷리스트"} if state.get("target_part") else set())
    check = state.get("check") or {}
    if "used" in check and "fake_citations" in check:
        return list(check["used"]), list(check["fake_citations"]), cards
    cited = citations(answer)
    return sorted(cited & valid), sorted(cited - valid), cards


def judgement_parts(judgement: dict) -> list[dict]:
    """답 글에 조건 표와 인용이 실제로 나간 후보 목록(판정은 results, 찾기는 보여 준 후보 shown만)."""
    # [왜] 찾기의 results에는 판정한 후보 전체(최대 50개)가 들어 있지만 답 글에는 shown만 조건 표와 인용이 나간다.
    # results로 세면 답에 안 보인 후보의 인용으로 정답이 맞을 수 있다(11-06 진단, cited_gold 3건)
    if judgement.get("kind") == "find":
        return list(judgement.get("shown") or [])
    return list(judgement.get("results") or [])


def judgement_locations(judgement: dict) -> list[list]:
    """판정 답이 인용한 (문서, 쪽) 목록. [왜] 판정 답은 [n] 청크 번호 대신 사양 표 행의 문서 · 쪽 · 표 · 행을 인용한다."""
    locs = []
    for part in judgement_parts(judgement):
        for c in part.get("checks") or []:
            cite = c.get("citation") or {}
            loc = [cite.get("document"), cite.get("page")]
            if cite and loc not in locs:
                locs.append(loc)
    return locs


def is_refusal_response(state: dict, used: list[str] | None = None) -> bool:
    """그래프 응답이 거절인지 판별한다.

    - 거절 노드로 끝났거나, 답이 비었거나, 범위 밖 안내이면 거절이다.
    - '문서로 확인 안 됨'으로 시작하더라도, 생성 노드를 거쳐 유효한 근거 번호(used)를 인용하며
      조건 부족(NOT_VERIFIED)을 설명한 응답은 거절이 아니라 근거 기반 답변으로 본다(n01, n02).
    """
    path = state.get("path") or []
    answer = (state.get("answer") or "").strip()
    if not answer or (path and path[-1] == "거절") or answer.startswith(OUT_OF_SCOPE_PREFIX):
        return True
    if used is None:
        used, _, _ = _used_and_fake(state, answer)
    if answer == NOT_FOUND or (answer.startswith(NOT_FOUND) and not used):
        return True
    return False


def score_item(item: dict, state: dict) -> dict:
    """문항 하나와 그래프 실행 상태 하나를 대조해 5지표 중 하나를 돌려준다."""
    answer = (state.get("answer") or "").strip()
    used, fake, cards = _used_and_fake(state, answer)
    refused = is_refusal_response(state, used)

    gold_chunks = item.get("gold_chunks") or []
    gold_locs = gold_locations(gold_chunks)
    needs_netlist = any(".net" in g for g in gold_chunks)

    cited_locs = []
    for cid in used:
        if cid in cards:
            card = cards[cid]
            loc = [card.get("file"), card.get("page")]
            if loc not in cited_locs:
                cited_locs.append(loc)
    cited_netlist = "넷리스트" in used
    if (state.get("check") or {}).get("judgement"):
        # 판정 길 답(코드 틀): 사양 표 인용 위치를 [n] 인용 위치와 같은 방식으로 정답 (PDF, 쪽)과 대조한다(사전 등록 #39 · #40)
        cited_locs = judgement_locations(state.get("judgement") or {})
        used = ["사양 표"] if cited_locs else []

    kind = item["kind"]
    if kind == "relevant":
        if refused:
            metric = "over_refusal"
        else:
            gold_set = {(f, p) for f, p in gold_locs}
            loc_hit = any((loc[0], loc[1]) in gold_set for loc in cited_locs) if gold_set else False
            if gold_set:
                evidence_ok = loc_hit
            elif needs_netlist:
                evidence_ok = cited_netlist
            else:
                evidence_ok = bool(used)
            metric = "cited_gold" if (evidence_ok and not fake and used) else "wrong_citation"
    elif kind == "irrelevant":
        metric = "correct_refusal" if refused else "hallucination_risk"
    else:
        raise ValueError(f"알 수 없는 kind: {kind}")

    return {
        "id": item["id"],
        "kind": kind,
        "question_type": item.get("question_type"),
        "irrelevant_type": item.get("irrelevant_type"),
        "metric": metric,
        "is_refusal": refused,
        "cited_locations": cited_locs,
        "cited_netlist": cited_netlist,
        "gold_locations": [[f, p] for f, p in gold_locs],
        "needs_netlist": needs_netlist,
        "fake_citations": fake,
    }


def _rate_block(ids: list[str], total: int) -> dict:
    return {
        "count": len(ids),
        "total": total,
        "rate": round(len(ids) / total, 3) if total > 0 else None,
        "ids": ids,
    }


def score_dataset(items: list[dict], states_by_id: dict[str, dict], *, excluded_ids: set[str] | None = None) -> dict:
    """평가셋 전체(제외 문항 반영)에 대해 5지표 요약과 문항별 채점 결과를 돌려준다."""
    excluded = excluded_ids or set()
    rows = []
    by_metric: dict[str, list[str]] = {m: [] for m in (*REL_METRICS, *IRR_METRICS)}
    missing_ids = []

    for it in items:
        qid = it["id"]
        if qid in excluded:
            continue
        if qid not in states_by_id:
            missing_ids.append(qid)
            continue
        row = score_item(it, states_by_id[qid])
        rows.append(row)
        by_metric[row["metric"]].append(qid)

    rel_total = sum(1 for r in rows if r["kind"] == "relevant")
    irr_total = sum(1 for r in rows if r["kind"] == "irrelevant")

    return {
        "evaluated": len(rows),
        "relevant_total": rel_total,
        "irrelevant_total": irr_total,
        "excluded_ids": sorted(excluded & {it["id"] for it in items}),
        "candidate_find_ids": [r["id"] for r in rows if r.get("question_type") == "candidate_find"],
        "missing_ids": missing_ids,
        "metrics": {
            "cited_gold_rate": _rate_block(by_metric["cited_gold"], rel_total),
            "wrong_citation_rate": _rate_block(by_metric["wrong_citation"], rel_total),
            "over_refusal_rate": _rate_block(by_metric["over_refusal"], rel_total),
            "correct_refusal_rate": _rate_block(by_metric["correct_refusal"], irr_total),
            "hallucination_risk_rate": _rate_block(by_metric["hallucination_risk"], irr_total),
        },
        "rows": rows,
    }


def _extract_states(raw: dict | list) -> dict[str, dict[str, dict]]:
    """실행 결과 JSON에서 모드별 {mode: {id: state}} 사전을 뽑는다.

    - run_skill_pair.py 형식: rows[].state + rows[].answers.{without, with} -> {"without": ..., "with": ...}
    - 단일 실행 형식: rows[].id + rows[].state 또는 {id: state} -> {"default": ...}
    """
    if isinstance(raw, dict) and isinstance(raw.get("rows"), list):
        rows = raw["rows"]
        if rows and "answers" in rows[0]:
            modes: dict[str, dict[str, dict]] = {}
            for r in rows:
                base = r.get("state") or {}
                for mode, ans in (r.get("answers") or {}).items():
                    merged = {**base, **ans}
                    if base.get("path") and merged["path"][-1] not in ("생성", "거절"):
                        merged["path"] = [*base["path"], *(ans.get("path") or [])]
                    modes.setdefault(mode, {})[r["id"]] = merged
            return modes
        return {"default": {r["id"]: r.get("state", r) for r in rows if "id" in r}}
    if isinstance(raw, list):
        return {"default": {r["id"]: r.get("state", r) for r in raw if isinstance(r, dict) and "id" in r}}
    if isinstance(raw, dict):
        return {"default": {k: v for k, v in raw.items() if isinstance(v, dict)}}
    raise ValueError("지원하지 않는 실행 결과 JSON 형식입니다")


def main(dataset_path: str, run_json_path: str, out_path: str | None = None) -> int:
    items = [json.loads(line) for line in Path(dataset_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    raw = json.loads(Path(run_json_path).read_text(encoding="utf-8"))
    excluded = load_excluded_ids()
    modes = _extract_states(raw)
    results = {mode: score_dataset(items, states, excluded_ids=excluded) for mode, states in modes.items()}
    output = results["default"] if list(results) == ["default"] else {"modes": results}
    if out_path:
        Path(out_path).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {mode: {k: {"count": v["count"], "total": v["total"], "rate": v["rate"]}
                      for k, v in res["metrics"].items()} for mode, res in results.items()}
    print(json.dumps(summary["default"] if list(summary) == ["default"] else summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit("사용법: python -m evals.runners.score_answer <평가셋 jsonl> <실행 결과 json> [채점 결과 json]")
    raise SystemExit(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None))
