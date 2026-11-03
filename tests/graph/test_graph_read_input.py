"""입력 읽기 노드: 입력 글 나누기와 넷리스트 2단계 읽기를 확인한다.

- 역할: e01에서 J1 -> S1 -> D1 -> F1 -> RAW 경로가 보이는지, 큰 넷 자르기, 평가셋 v1 50문항 모두 대상 부품을 읽는지 확인한다.
- 하지 않는 일: LLM·검색·DB를 쓰지 않는다. 읽은 부품이 맞는 후보인지의 판정은 하지 않는다.
- 출처: SPEC 2절 노드 표, evals/dataset_v1.jsonl(동결)
"""
import json

from backend.graph.nodes import circuit_around, parse_input, read_input

E01 = ("회로: SparkFun Breadboard Supply\n"
       "넷리스트: data/circuits/collected/samples/breadboard_supply/converted/circuit.net\n"
       "대상: D1\n사용 조건: 전원은 J1 잭으로만 공급한다.\n질문: 이 보드에서 D1은 왜 필요한 거야?")


def test_parse_input_splits_fields():
    fields = parse_input(E01)
    assert fields["target"] == "D1"
    assert fields["conditions"] == "전원은 J1 잭으로만 공급한다."
    assert fields["question"] == "이 보드에서 D1은 왜 필요한 거야?"
    assert fields["netlist_path"].endswith("breadboard_supply/converted/circuit.net")


def test_free_text_becomes_question():
    assert parse_input("1N4148 대신 뭐 써?") == {"question": "1N4148 대신 뭐 써?"}


def test_read_input_shows_power_path_two_steps_away():
    # 비교 시험 e01에서 대상 부품의 넷만 넣었더니 J1 → S1 → D1 → F1 경로가 안 보였다. 2단계로 읽으면 보여야 한다
    out = read_input({"input": E01})
    part = out["target_part"]
    assert (part["ref"], part["value"]) == ("D1", "1N4001")
    shown = " ".join(" ".join(net["nodes"]) for net in part["nets"])
    for piece in ("S1.", "F1.", "J1.PWR", "U1.IN"):
        assert piece in shown
    assert out["path"] == ["입력 읽기"]


def test_read_input_clears_previous_search_state():
    out = read_input({"input": E01, "query": "old", "parts": ["OLD"], "docs": [{"chunk_id": 1}],
                      "passed": [1], "retrieval_error": {"kind": "timeout"}, "tries": 2})
    assert out["query"] == "" and out["parts"] == [] and out["docs"] == [] and out["passed"] == []
    assert out["retrieval_error"] is None
    assert out["tries"] == -2


def test_big_nets_are_cut_and_counted():
    nodes = [{"ref": f"C{i}", "pin": "1"} for i in range(12)] + [{"ref": "R1", "pin": "1"}]
    connections = {"components": [{"ref": "R1", "value": "10k"}], "nets": [{"name": "GND", "nodes": nodes}]}
    net = circuit_around(connections, "R1")["nets"][0]
    assert len(net["nodes"]) == 8 and net["more"] == 5


def test_every_v1_input_is_read():
    # 동결 평가셋 50문항 모두에서 질문과 대상 부품을 읽어야 한다(넷리스트 5종, c09는 한 단계 위 폴더)
    rows = [json.loads(line) for line in open("evals/dataset_v1.jsonl", encoding="utf-8")]
    assert len(rows) == 50
    for row in rows:
        out = read_input({"input": row["input"]})
        assert out["question"], row["id"]
        assert out["target_part"].get("ref") == out["target"], row["id"]


def test_netlist_path_outside_repo_gives_no_circuit_context(tmp_path):
    # 저장소 밖의 connections.json을 ../ 나 절대 경로로 가리켜도 읽지 않는다
    (tmp_path / "connections.json").write_text(
        json.dumps({"components": [{"ref": "D1", "value": "X"}], "nets": []}), encoding="utf-8")
    for bad in (str(tmp_path / "circuit.net"), "../" * 12 + str(tmp_path).lstrip("/") + "/circuit.net"):
        out = read_input({"input": f"넷리스트: {bad}\n대상: D1\n질문: D1 역할?"})
        assert out["target_part"] == {}, bad
