"""입력 읽기 노드: 입력 글 나누기와 넷리스트 2단계 읽기를 확인한다.

- 역할: e01에서 J1 -> S1 -> D1 -> F1 -> RAW 경로가 보이는지, 큰 넷 자르기, 평가셋 v1 50문항 모두 대상 부품을 읽는지 확인한다.
- 하지 않는 일: LLM·검색·DB를 쓰지 않는다. 읽은 부품이 맞는 후보인지의 판정은 하지 않는다.
- 출처: SPEC 2절 노드 표, evals/dataset_v1.jsonl(동결)
"""
import json

from backend.graph.nodes import MAX_NET_NODES, circuit_around, parse_input, read_input

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
                      "passed": [1], "retrieval_error": {"kind": "timeout"}, "tries": 2, "facts": {"parts": {"OLD": False}},
                      "refusal": {"code": "part_missing"}, "judge_read": {"role": "R01"}, "judgement": {"kind": "judge"}})
    assert out["query"] == "" and out["parts"] == [] and out["docs"] == [] and out["passed"] == []
    assert out["retrieval_error"] is None
    assert out["tries"] == -2
    assert out["facts"] == {}  # [왜] 앞 질문의 사실 확인 결과로 새 질문을 거절하지 않게 한다
    assert out["refusal"] == {}  # 앞 질문의 거절 사유 코드가 새 질문의 채점에 남지 않게 한다
    assert out["judge_read"] == {} and out["judgement"] == {}  # 앞 질문의 판정으로 새 질문에 답하지 않게 한다


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


def test_target_pin_is_always_shown_in_a_big_net():
    """AC-10: 노드가 많은 GND 넷에서도 대상 자신의 핀이 보인다(앞 MAX_NET_NODES개에 들지 않아도)."""
    others = [{'ref': f'C{i}', 'pin': '2'} for i in range(MAX_NET_NODES + 3)]
    connections = {'components': [{'ref': 'D1', 'value': 'BZT52C3V6', 'footprint': 'SOD-123'}] +
                                 [{'ref': n['ref'], 'value': '100n', 'footprint': '0603'} for n in others],
                   'nets': [{'name': 'GND', 'nodes': others + [{'ref': 'D1', 'pin': '1', 'pinfunction': 'A'}]}]}
    gnd = circuit_around(connections, 'D1')['nets'][0]
    assert any(n.startswith('D1.') for n in gnd['nodes']) and len(gnd['nodes']) == MAX_NET_NODES


def test_nearby_pin_context_keeps_declared_functions_and_hidden_capacitor():
    from backend.graph.nodes import netlist_block
    nodes = [{'ref': f'R{i}', 'pin': '1'} for i in range(MAX_NET_NODES + 1)]
    nodes += [{'ref': 'C2', 'pin': '1'}, {'ref': 'D1', 'pin': '1', 'pinfunction': 'K'}]
    parts = [{'ref': n['ref'], 'value': '10k'} for n in nodes]
    parts += [{'ref': 'Q1', 'value': 'Q_NPN_CBE'}]
    circuit = {'components': parts, 'nets': [
        {'name': 'VCC', 'nodes': nodes},
        {'name': 'SW', 'nodes': [{'ref':'D1','pin':'2','pinfunction':'A'},
                                {'ref':'Q1','pin':'1','pinfunction':'C'}]}]}
    around = circuit_around(circuit, 'D1')
    context = {p['ref']:p for p in around['context_components']}
    assert context['Q1']['pins'][0] == {'pin':'1','function':'C','net':'SW'}
    assert context['C2']['pins'][0]['net'] == 'VCC'
    rendered = netlist_block(around)
    assert '1 (C) = SW' in rendered and 'C2' in rendered


def test_boost_mechanism_uses_declared_polarity_and_actual_output_capacitor():
    from backend.graph.nodes import circuit_mechanism
    def pins(*items):
        return [{'pin':str(i),'function':function,'net':net} for i,(function,net) in enumerate(items,1)]
    part = {'ref':'D7','pins':pins(('A','SW'),('K','OUT')), 'context_components':[
        {'ref':'L8','value':'L','symbol':'Device:L','pins':pins(('1','INPUT'),('2','SW'))},
        {'ref':'U9','value':'controller','pins':pins(('LX','SW'),('VOUT','OUT'))},
        {'ref':'C1','value':'input cap','pins':pins(('1','INPUT'),('2','GND'))},
        {'ref':'C7','value':'output cap','pins':pins(('1','OUT'),('2','GND'))}]}
    answer = circuit_mechanism(part)
    assert 'C7' in answer and 'input cap' not in answer
    assert 'A→K' in answer and '에너지가 저장' in answer
    part['pins'] = pins(('', 'SW'),('', 'OUT'))
    assert circuit_mechanism(part) == ''


def test_flyback_mechanism_closes_locally_without_claiming_supply_return():
    from backend.graph.nodes import circuit_mechanism
    part = {'ref':'D7','pins':[{'pin':'2','function':'A','net':'COIL_LOW'},
                              {'pin':'1','function':'K','net':'COIL_HIGH'}],
            'context_components':[
                {'ref':'LS8','symbol':'Device:Buzzer','pins':[
                    {'pin':'N','function':'','net':'COIL_LOW'},
                    {'pin':'P','function':'','net':'COIL_HIGH'}]},
                {'ref':'Q9','pins':[{'pin':'1','function':'C','net':'COIL_LOW'},
                                    {'pin':'3','function':'E','net':'GND'}]}]}
    answer = circuit_mechanism(part)
    assert 'D7.A → D7.K' in answer and '국소 순환' in answer
    assert '반드시 반환' in answer and '확정할 수는 없습니다' in answer


def test_flyback_mechanism_keeps_shared_rail_resistor_pin_numbers():
    from backend.graph.nodes import circuit_mechanism
    part = {'ref':'D1','pins':[{'pin':'2','function':'A','net':'COIL_LOW'},
                              {'pin':'1','function':'K','net':'COIL_HIGH'}],
            'context_components':[
                {'ref':'LS1','value':'KTG0912CL','symbol':'Device:Buzzer','pins':[
                    {'pin':'N','function':'','net':'COIL_LOW'}, {'pin':'P','function':'','net':'COIL_HIGH'}]},
                {'ref':'Q1','value':'Q_NPN_CBE','pins':[{'pin':'1','function':'C','net':'COIL_LOW'},
                                                       {'pin':'3','function':'E','net':'GND'}]},
                {'ref':'R22','value':'100R','pins':[{'pin':'1','function':'','net':'+5V'},
                                                   {'pin':'2','function':'','net':'COIL_HIGH'}]}]}
    answer = circuit_mechanism(part)
    assert 'R22' in answer and 'R22.1=+5V' in answer and 'R22.2=COIL_HIGH' in answer


def test_boost_mechanism_does_not_infer_topology_from_numeric_pins_only():
    from backend.graph.nodes import circuit_mechanism
    part = {'ref':'D1','libsource':'Diode:1N5817',
            'pins':[{'pin':'2','function':'','net':'SW'}, {'pin':'1','function':'','net':'VCC'}],
            'context_components':[
                {'ref':'BT1','value':'1xAAA','symbol':'Device:Battery','pins':[
                    {'pin':'1','function':'','net':'/Vbat'}, {'pin':'2','function':'','net':'GND'}]},
                {'ref':'L1','value':'100uH','symbol':'Device:L','pins':[
                    {'pin':'1','function':'','net':'/Vbat'}, {'pin':'2','function':'','net':'SW'}]},
                {'ref':'U1','value':'HT7733A','pins':[{'pin':'5','function':'','net':'SW'},
                                                     {'pin':'1','function':'','net':'VCC'}]},
                {'ref':'C2','value':'22uF','pins':[{'pin':'1','function':'','net':'VCC'},
                                                  {'pin':'2','function':'','net':'GND'}]}]}
    assert circuit_mechanism(part) == ''
