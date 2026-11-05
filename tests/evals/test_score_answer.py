"""답변·거절 5지표 채점기 테스트. API·DB 없이 돈다.

- 역할: 데이터시트·회로 전용 관련 문항의 정답 근거 인용(cited_gold), 다른 쪽·허위 번호 인용 시 오답 근거(wrong_citation),
  n01 등 relevant + NOT_VERIFIED에서 근거 인용 설명과 단순 거절(over_refusal) 구분, 비관련 4종의 올바른 거절(correct_refusal)
  대 환각 위험(hallucination_risk), v1 50문항·v2 70문항 분모·exclusions.json 제외 처리 및 run_graph.py 점수 연결을 확인한다.
- 하지 않는 일: 실제 LLM·DB 호출.
- 출처: docs/experiments/answer-refusal-scorer.md AC-01~AC-06, evals/runners/score_answer.py
"""
import json
from pathlib import Path

import pytest

from evals.runners.run_graph import run_scores
from evals.runners.score_answer import main, score_dataset, score_item

ROOT = Path(__file__).resolve().parents[2]

DATASHEET_ITEM = {
    "id": "draft30-e03",
    "kind": "relevant",
    "irrelevant_type": None,
    "expected": "TSC 1N5817의 반복 피크 역전압 정격 VRRM은 20 V이다.",
    "gold_chunks": ["1N5817 SERIES_H2104.pdf, 1쪽, ABSOLUTE MAXIMUM RATINGS, VRRM 20V"],
}

CIRCUIT_ONLY_ITEM = {
    "id": "draft30-e01",
    "kind": "relevant",
    "irrelevant_type": None,
    "expected": "D1은 역극성 보호 다이오드로 해석한다.",
    "gold_chunks": ["data/circuits/collected/samples/breadboard_supply/converted/circuit.net, D1.A・S1.3 = Net-(S1-S)"],
}

NOT_VERIFIED_RELEVANT_ITEM = {
    "id": "draft50-n01",
    "kind": "relevant",
    "irrelevant_type": None,
    "expected": "판정은 문서로 확인 안 됨(NOT_VERIFIED)이다. H2104 1쪽 기본 조건은 TA=25°C이고 질문은 TJ=25°C만 제공한다.",
    "gold_chunks": ["1N5817 SERIES_H2104.pdf, 1쪽, ABSOLUTE MAXIMUM RATINGS (TA=25°C unless otherwise noted)",
                    "data/circuits/collected/samples/mosfet_driver/converted/circuit.net, D3 핀 A=/OUT"],
}

IRRELEVANT_ITEMS = [
    {"id": "draft30-e06", "kind": "irrelevant", "irrelevant_type": "out_of_domain", "expected": "범위 밖 거절", "gold_chunks": []},
    {"id": "draft30-e07", "kind": "irrelevant", "irrelevant_type": "unknown_entity", "expected": "자료 부재 안내", "gold_chunks": []},
    {"id": "draft30-e09", "kind": "irrelevant", "irrelevant_type": "missing_attribute", "expected": "실측값 부재 안내", "gold_chunks": []},
    {"id": "draft30-e10", "kind": "irrelevant", "irrelevant_type": "wrong_period", "expected": "2026년판 부재 안내", "gold_chunks": []},
]


def test_ac01_datasheet_relevant_cited_gold():
    state = {
        "path": ["입력 읽기", "라우팅", "검색", "채점", "생성"],
        "docs": [{"chunk_id": 7, "file": "1N5817 SERIES_H2104.pdf", "page": 1, "content": "VRRM 20V"}],
        "passed": [7],
        "answer": "TSC 1N5817의 반복 피크 역전압 VRRM은 20 V입니다 [7].",
        "check": {"fake_citations": [], "uncited_sentences": 0, "used": ["7"]},
    }
    scored = score_item(DATASHEET_ITEM, state)
    assert scored["metric"] == "cited_gold"
    assert scored["is_refusal"] is False
    assert scored["cited_locations"] == [["1N5817 SERIES_H2104.pdf", 1]]


def test_ac02_circuit_only_relevant_requires_netlist_citation():
    part = {"ref": "D1", "value": "1N4001", "footprint": "DIODE", "nets": []}
    good_state = {
        "path": ["입력 읽기", "라우팅", "생성"],
        "target_part": part,
        "answer": "D1은 J1 전원 경로의 역극성 보호 다이오드입니다 [넷리스트].",
        "check": {"fake_citations": [], "uncited_sentences": 0, "used": ["넷리스트"]},
    }
    assert score_item(CIRCUIT_ONLY_ITEM, good_state)["metric"] == "cited_gold"

    no_cite_state = {
        "path": ["입력 읽기", "라우팅", "생성"],
        "target_part": part,
        "answer": "D1은 J1 전원 경로의 역극성 보호 다이오드입니다.",
        "check": {"fake_citations": [], "uncited_sentences": 1, "used": []},
    }
    assert score_item(CIRCUIT_ONLY_ITEM, no_cite_state)["metric"] == "wrong_citation"


def test_ac03_relevant_wrong_page_or_fake_citation_is_wrong_citation():
    wrong_page_state = {
        "path": ["입력 읽기", "라우팅", "검색", "채점", "생성"],
        "docs": [{"chunk_id": 8, "file": "1N5817 SERIES_H2104.pdf", "page": 2, "content": "VF 0.45V"}],
        "passed": [8],
        "answer": "순방향 전압은 0.45 V입니다 [8].",
        "check": {"fake_citations": [], "uncited_sentences": 0, "used": ["8"]},
    }
    assert score_item(DATASHEET_ITEM, wrong_page_state)["metric"] == "wrong_citation"

    fake_cite_state = {
        "path": ["입력 읽기", "라우팅", "검색", "채점", "생성"],
        "docs": [{"chunk_id": 7, "file": "1N5817 SERIES_H2104.pdf", "page": 1, "content": "VRRM 20V"}],
        "passed": [7],
        "answer": "VRRM은 20 V입니다 [7]. IF는 1 A입니다 [999].",
        "check": {"fake_citations": ["999"], "uncited_sentences": 0, "used": ["7"]},
    }
    assert score_item(DATASHEET_ITEM, fake_cite_state)["metric"] == "wrong_citation"


def test_ac04_relevant_not_verified_distinguishes_cited_explanation_from_bare_refusal():
    cited_not_verified = {
        "path": ["입력 읽기", "라우팅", "검색", "채점", "생성"],
        "docs": [{"chunk_id": 1, "file": "1N5817 SERIES_H2104.pdf", "page": 1, "content": "TA=25C VRRM 20V IFSM 30A"}],
        "passed": [1],
        "answer": "문서로 확인 안 됨(NOT_VERIFIED): H2104 1쪽 정격은 TA=25°C 기준이나 질문은 TJ=25°C만 제시합니다 [1].",
        "check": {"fake_citations": [], "uncited_sentences": 0, "used": ["1"]},
    }
    scored = score_item(NOT_VERIFIED_RELEVANT_ITEM, cited_not_verified)
    assert scored["metric"] == "cited_gold"
    assert scored["is_refusal"] is False

    refuse_node_state = {
        "path": ["입력 읽기", "라우팅", "검색", "채점", "거절"],
        "docs": [],
        "passed": [],
        "answer": "문서로 확인 안 됨: 1N5817 데이터시트를 찾지 못했습니다.",
        "check": {},
    }
    assert score_item(NOT_VERIFIED_RELEVANT_ITEM, refuse_node_state)["metric"] == "over_refusal"

    bare_not_found_state = {
        "path": ["입력 읽기", "라우팅", "검색", "채점", "생성"],
        "docs": [{"chunk_id": 1, "file": "1N5817 SERIES_H2104.pdf", "page": 1, "content": "TA=25C"}],
        "passed": [1],
        "answer": "문서로 확인 안 됨",
        "check": {"fake_citations": [], "uncited_sentences": 0, "used": []},
    }
    assert score_item(NOT_VERIFIED_RELEVANT_ITEM, bare_not_found_state)["metric"] == "over_refusal"


@pytest.mark.parametrize("item", IRRELEVANT_ITEMS)
def test_ac05_irrelevant_correct_refusal_vs_hallucination_risk(item):
    refusal_state = {
        "path": ["입력 읽기", "라우팅", "거절"],
        "answer": "이 질문은 SojaFit 범위 밖입니다." if item["irrelevant_type"] == "out_of_domain"
                  else "문서로 확인 안 됨: 질문에 맞는 근거를 찾지 못했습니다.",
        "check": {},
    }
    assert score_item(item, refusal_state)["metric"] == "correct_refusal"

    gen_not_found_state = {
        "path": ["입력 읽기", "라우팅", "검색", "채점", "생성"],
        "docs": [{"chunk_id": 2, "file": "1N5817 SERIES_H2104.pdf", "page": 1, "content": "VRRM 20V"}],
        "passed": [2],
        "answer": "문서로 확인 안 됨",
        "check": {"fake_citations": [], "uncited_sentences": 0, "used": []},
    }
    assert score_item(item, gen_not_found_state)["metric"] == "correct_refusal"

    hallucinated_state = {
        "path": ["입력 읽기", "라우팅", "검색", "채점", "생성"],
        "docs": [{"chunk_id": 2, "file": "1N5817 SERIES_H2104.pdf", "page": 1, "content": "VRRM 20V"}],
        "passed": [2],
        "answer": "요청하신 2026년판 역전압 정격은 20 V입니다 [2].",
        "check": {"fake_citations": [], "uncited_sentences": 0, "used": ["2"]},
    }
    assert score_item(item, hallucinated_state)["metric"] == "hallucination_risk"


def test_ac06_score_dataset_denominators_and_exclusions_on_v1_and_v2(tmp_path):
    v1_path = ROOT / "evals" / "dataset_v1.jsonl"
    v2_path = ROOT / "evals" / "dataset_v2.jsonl"
    items_v1 = [json.loads(line) for line in v1_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    items_v2 = [json.loads(line) for line in v2_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(items_v1) == 50
    assert len(items_v2) == 70

    states = {}
    for it in items_v2:
        if it["kind"] == "relevant":
            pdf_golds = [g for g in it["gold_chunks"] if ".pdf" in g]
            if pdf_golds:
                pdf, page_part = pdf_golds[0].split(".pdf,", 1)
                page = int(page_part.strip().split("쪽")[0])
                states[it["id"]] = {
                    "path": ["입력 읽기", "라우팅", "검색", "채점", "생성"],
                    "docs": [{"chunk_id": 1, "file": f"{pdf}.pdf", "page": page, "content": "ok"}],
                    "passed": [1],
                    "answer": "근거 확인 [1].",
                    "check": {"fake_citations": [], "uncited_sentences": 0, "used": ["1"]},
                }
            else:
                states[it["id"]] = {
                    "path": ["입력 읽기", "라우팅", "생성"],
                    "target_part": {"ref": "D1"},
                    "answer": "회로 연결 확인 [넷리스트].",
                    "check": {"fake_citations": [], "uncited_sentences": 0, "used": ["넷리스트"]},
                }
        else:
            states[it["id"]] = {
                "path": ["입력 읽기", "라우팅", "거절"],
                "answer": "문서로 확인 안 됨: 근거 없음.",
                "check": {},
            }

    # 일부러 관련 1건은 오답 근거, 관련 1건은 과잉 거절, 비관련 1건은 환각 위험으로 만들고 비관련 1건(draft50-n15)은 제외
    states["draft30-e03"]["answer"] = "근거 없는 답."
    states["draft30-e03"]["check"] = {"fake_citations": [], "uncited_sentences": 1, "used": []}
    states["draft30-e04"] = {"path": ["입력 읽기", "라우팅", "거절"], "answer": "문서로 확인 안 됨", "check": {}}
    states["draft30-e06"] = {
        "path": ["입력 읽기", "라우팅", "생성"],
        "docs": [{"chunk_id": 1, "file": "x.pdf", "page": 1, "content": "x"}],
        "passed": [1],
        "answer": "AO3406 대신 2N7002를 쓰세요 [1].",
        "check": {"fake_citations": [], "uncited_sentences": 0, "used": ["1"]},
    }

    summary_v1 = score_dataset(items_v1, states, excluded_ids={"draft50-n15"})
    m1 = summary_v1["metrics"]
    assert summary_v1["relevant_total"] == 25
    assert summary_v1["irrelevant_total"] == 24
    assert summary_v1["excluded_ids"] == ["draft50-n15"]
    assert m1["cited_gold_rate"]["count"] + m1["wrong_citation_rate"]["count"] + m1["over_refusal_rate"]["count"] == 25
    assert m1["correct_refusal_rate"]["count"] + m1["hallucination_risk_rate"]["count"] == 24
    assert m1["cited_gold_rate"]["count"] == 23 and m1["wrong_citation_rate"]["ids"] == ["draft30-e03"]
    assert m1["over_refusal_rate"]["ids"] == ["draft30-e04"]
    assert m1["hallucination_risk_rate"]["ids"] == ["draft30-e06"]

    summary_v2 = score_dataset(items_v2, states, excluded_ids={"draft50-n15"})
    assert summary_v2["relevant_total"] == 35
    assert summary_v2["irrelevant_total"] == 34
    assert len(summary_v2["candidate_find_ids"]) == 10

    pair_file = tmp_path / "pair.json"
    out_file = tmp_path / "scored.json"
    pair_rows = [{"id": it["id"], "state": states[it["id"]],
                  "answers": {"without": {"answer": states[it["id"]]["answer"], "check": states[it["id"]]["check"]},
                              "with": {"answer": states[it["id"]]["answer"], "check": states[it["id"]]["check"]}}}
                 for it in items_v1]
    pair_file.write_text(json.dumps({"rows": pair_rows}, ensure_ascii=False), encoding="utf-8")
    assert main(str(v1_path), str(pair_file), str(out_file)) == 0
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert set(saved["modes"]) == {"without", "with"}
    assert saved["modes"]["with"]["metrics"]["cited_gold_rate"]["count"] == 23


def test_run_graph_scores_include_answer_metric_when_item_given():
    state = {
        "path": ["입력 읽기", "라우팅", "검색", "채점", "생성"],
        "question_type": "rating",
        "tries": 1,
        "docs": [{"chunk_id": 7, "file": "1N5817 SERIES_H2104.pdf", "page": 1}],
        "passed": [7],
        "answer": "VRRM은 20 V다 [7].",
        "check": {"fake_citations": [], "uncited_sentences": 0, "used": ["7"]},
    }
    scores = run_scores(state, 1.2, ["Route", "Grade", "Answer"], item=DATASHEET_ITEM)
    assert scores["answer_metric"][:2] == ("cited_gold", "CATEGORICAL")


def _judge_state(document, page):
    """판정 길 답 상태: 코드 틀 답(check.judgement)과 사양 표 인용이 달린 판정 결과."""
    check = {"code": "VRRM", "citation": {"document": document, "page": page, "table": "ABSOLUTE MAXIMUM RATINGS", "row": "VRRM"}}
    return {"path": ["입력 읽기", "판정", "답 틀"], "answer": "역할: 역극성 보호\n\n**1N5817: 불충족**",
            "check": {"used": [], "judgement": True},
            "judgement": {"kind": "judge", "results": [{"part": "1N5817", "verdict": "NOT_SUFFICIENT", "checks": [check]}]}}


def test_judge_answer_citing_gold_page_is_cited_gold():
    """판정 답이 사양 표로 정답 (PDF, 쪽)을 인용하면 [n] 인용과 같이 cited_gold다(사전 등록 #39 · #40)."""
    row = score_item(DATASHEET_ITEM, _judge_state("1N5817 SERIES_H2104.pdf", 1))
    assert row["metric"] == "cited_gold"
    assert row["cited_locations"] == [["1N5817 SERIES_H2104.pdf", 1]]


def test_judge_answer_citing_other_page_is_wrong_citation():
    """판정 답의 사양 표 인용이 정답 쪽이 아니면 wrong_citation이다."""
    assert score_item(DATASHEET_ITEM, _judge_state("1N5817 SERIES_H2104.pdf", 2))["metric"] == "wrong_citation"


def test_result_row_keeps_verdict_codes_only():
    """결과 줄에는 후보별 판정 코드만 남고 답 글은 남지 않는다."""
    from evals.runners.run_graph import result_row
    scores = {"question_type": ("candidate_judge", "CATEGORICAL", ""), "answer_metric": ("cited_gold", "CATEGORICAL", "")}
    row = result_row(DATASHEET_ITEM, _judge_state("1N5817 SERIES_H2104.pdf", 1), scores, "")
    assert row["verdicts"] == [["1N5817", "NOT_SUFFICIENT"]]
    assert "answer" not in row


def test_find_answer_counts_only_shown_candidates():
    """찾기 답은 답 글에 나간 후보(shown)의 인용만 센다. 판정만 하고 안 보여 준 후보의 인용으로 정답이 되지 않는다."""
    gold = {"document": "1N5817 SERIES_H2104.pdf", "page": 1}
    other = {"document": "SS12 SERIES_R2305.pdf", "page": 1}
    hidden = {"part": "1N5817", "verdict": "ROLE_SUFFICIENT", "checks": [{"code": "VRRM", "citation": gold}]}
    shown = {"part": "SS14", "verdict": "ROLE_SUFFICIENT", "checks": [{"code": "VRRM", "citation": other}]}
    state = {"path": ["판정", "답 틀"], "answer": "역할: 역극성 보호", "check": {"used": [], "judgement": True},
             "judgement": {"kind": "find", "results": [hidden, shown], "shown": [shown], "unverified": []}}
    assert score_item(DATASHEET_ITEM, state)["metric"] == "wrong_citation"
