"""합성 KiCad 입력의 제한·문법·불변 정규화와 원본 폐기를 확인한다."""
import hashlib
import importlib
import importlib.util
from dataclasses import fields, FrozenInstanceError
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parents[1] / "fixtures/netlists"
MAX_BYTES = 5 * 1024 * 1024


def parser():
    assert importlib.util.find_spec("backend.projects.netlist") is not None, "bounded KiCad normalizer is missing"
    return importlib.import_module("backend.projects.netlist")


def test_circuit_fingerprint_uses_components_and_pin_partition():
    import json
    base=json.loads(json.dumps(parser().normalize_netlist((FIXTURES/'minimal.net').read_bytes()).connections,default=dict))
    same=json.loads(json.dumps(base));same['parts'].reverse();same['nets'][0]['nodes'].reverse()
    same['nets'][0].update(code='99',name='renamed')
    assert parser().circuit_fingerprint(base)==parser().circuit_fingerprint(same)
    for change in ('pin','value','split'):
        other=json.loads(json.dumps(base))
        if change=='pin':other['nets'][0]['nodes'][0]['pin']='9'
        elif change=='value':other['parts'][0]['value']='1N4007'
        else:
            node=other['nets'][0]['nodes'].pop()
            other['nets'].append({'code':'2','name':'isolated','nodes':[node]})
        assert parser().circuit_fingerprint(base)!=parser().circuit_fingerprint(other)
    duplicate=json.loads(json.dumps(base));duplicate['nets'].append(duplicate['nets'][0])
    with pytest.raises(parser().InvalidNetlist):parser().circuit_fingerprint(duplicate)


def _cycle_circuit(lengths, offset=0):
    refs = [f'R{i + offset}' for i in range(sum(lengths))]
    nets, start = [], 0
    for size in lengths:
        cycle = refs[start:start + size]
        nets.extend({'nodes': [{'ref': ref, 'pin': '2'},
                               {'ref': cycle[(i + 1) % size], 'pin': '1'}]}
                    for i, ref in enumerate(cycle))
        start += size
    return {'parts': [{'ref': ref, 'value': '1k', 'footprint': 'R_0603'} for ref in refs], 'nets': nets}


def _scrambled_cycles(lengths, seed):
    import random
    circuit = _cycle_circuit(lengths)
    names = [f'R{i + 1000}' for i in range(sum(lengths))]
    random.Random(seed).shuffle(names)
    refs = {part['ref']: name for part, name in zip(circuit['parts'], names)}
    return {'parts': [{**part, 'ref': refs[part['ref']]} for part in circuit['parts']],
            'nets': [{'nodes': [{**node, 'ref': refs[node['ref']]} for node in net['nodes']]}
                     for net in circuit['nets']]}


@pytest.mark.parametrize('lengths', [[120], [200], [240], [60, 60, 60, 60]])
@pytest.mark.parametrize('seed', [1, 7, 19])
def test_large_symmetric_circuits_survive_random_reference_order(lengths, seed):
    assert parser().same_circuit(_cycle_circuit(lengths), _scrambled_cycles(lengths, seed))


def test_anchored_symmetry_is_resolved_without_spending_steps_on_impossible_pairs(monkeypatch):
    monkeypatch.setattr(parser(), 'MAX_MATCH_STEPS', 240)
    assert parser().same_circuit(_cycle_circuit([240]), _scrambled_cycles([240], 7))
    assert not parser().same_circuit(_cycle_circuit([240]), _scrambled_cycles([120, 120], 7))


def test_renumbered_symmetric_parts_require_a_complete_connection_mapping():
    left, right = _cycle_circuit([6]), _cycle_circuit([6], 100)
    right['parts'].reverse()
    right['nets'].reverse()
    assert parser().circuit_fingerprint(left) != parser().circuit_fingerprint(right)
    assert parser().same_circuit(left, right)
    # All local part/pin/net degrees are equal, but the complete circuits differ.
    assert not parser().same_circuit(left, _cycle_circuit([3, 3], 100))


@pytest.mark.parametrize('change', ['pin', 'value', 'footprint', 'prefix', 'missing'])
def test_renumbering_cannot_hide_a_different_circuit(change):
    import json
    left = json.loads(json.dumps(parser().normalize_netlist((FIXTURES/'minimal.net').read_bytes()).connections, default=dict))
    right = json.loads(json.dumps(left))
    for part in right['parts']:
        part['ref'] += '00'
    for net in right['nets']:
        for node in net['nodes']:
            node['ref'] += '00'
    assert parser().same_circuit(left, right)
    if change == 'pin': right['nets'][0]['nodes'][0]['pin'] = '1'
    elif change == 'value': right['parts'][0]['value'] = '1N4007'
    elif change == 'footprint': right['parts'][0]['footprint'] = 'D_SMA'
    elif change == 'prefix':
        right['parts'][0]['ref'] = 'X100'
        right['nets'][0]['nodes'][0]['ref'] = 'X100'
    else:
        right['parts'].append({'ref': 'C100', 'value': '1n', 'footprint': ''})
    assert not parser().same_circuit(left, right)


@pytest.mark.parametrize('limit', ['MAX_MATCH_STEPS', 'MAX_MATCH_SECONDS', 'MAX_MATCH_PARTS', 'MAX_MATCH_NETS', 'MAX_MATCH_PINS'])
def test_renumber_match_fails_closed_at_search_and_size_limits(monkeypatch, limit):
    monkeypatch.setattr(parser(), limit, 0)
    assert not parser().same_circuit(_cycle_circuit([6]), _cycle_circuit([6], 100))
    assert parser().same_circuit(_cycle_circuit([6]), _cycle_circuit([6]))


def test_small_circuit_matches_agree_with_exhaustive_reference_permutations():
    import itertools
    import random
    rng = random.Random(19)
    def make(offset):
        circuit = _cycle_circuit([4], offset)
        nodes = [node for net in circuit['nets'] for node in net['nodes']]
        rng.shuffle(nodes)
        cuts = sorted(rng.sample(range(1, len(nodes)), 3))
        circuit['nets'] = [{'nodes': nodes[a:b]} for a, b in zip([0, *cuts], [*cuts, len(nodes)])]
        return circuit
    def renamed(circuit, names):
        refs = {part['ref']: name for part, name in zip(circuit['parts'], names)}
        return {'parts': [{**part, 'ref': refs[part['ref']]} for part in circuit['parts']],
                'nets': [{'nodes': [{**node, 'ref': refs[node['ref']]} for node in net['nodes']]} for net in circuit['nets']]}
    for index in range(30):
        left = make(0)
        names = [f'R{i}' for i in range(100, 104)]
        rng.shuffle(names)
        right = renamed(left, names) if index % 2 == 0 else make(100)
        expected = any(parser().circuit_fingerprint(left) == parser().circuit_fingerprint(renamed(right, permutation))
                       for permutation in itertools.permutations(part['ref'] for part in left['parts']))
        assert parser().same_circuit(left, right) == expected
        assert parser().same_circuit(right, left) == expected


def test_normalize_exact_shape_hash_and_immutable_result():
    raw = (FIXTURES / "minimal.net").read_bytes()
    result = parser().normalize_netlist(raw)
    assert result.parts == ("D1", "R1")
    assert result.connections == {
        "parts": ({"ref": "D1", "value": "1N4148", "footprint": "Diode:SOD-123"},
                  {"ref": "R1", "value": "1k", "footprint": "Resistor:R_0603"}),
        "nets": ({"code": "1", "name": "GND", "nodes": ({"ref": "D1", "pin": "2"}, {"ref": "R1", "pin": "1"})},),
    }
    assert result.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert {f.name for f in fields(result)} == {"connections", "source_sha256", "parts"}
    assert "RAW_UPLOAD_MARKER" not in repr(result)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.source_sha256 = "changed"
    with pytest.raises(TypeError):
        result.connections["parts"][0]["value"] = "changed"


@pytest.mark.parametrize("raw", [
    b"\xff", b"", b"(not_export (components) (nets))", b"(export (nets))",
    b"(export (components))", b"(export (components) (nets))",
    (FIXTURES / "invalid.net").read_bytes(), b"(export))", b"(export) (export)",
    b"(export) trailing", b'(export (design (source "unterminated)))',
    b"(export (components (comp (ref D1))) (nets (net (code 1) (name GND) (node (ref UNKNOWN) (pin 1)))))",
])
def test_rejects_invalid_encoding_structure_and_unknown_nodes(raw):
    module = parser()
    with pytest.raises(module.InvalidNetlist):
        module.normalize_netlist(raw)


def test_size_is_rejected_before_decode_and_hash(monkeypatch):
    module = parser()
    def unexpected_hash(*args):
        pytest.fail("oversize bytes must be rejected before hashing")
    monkeypatch.setattr(module.hashlib, "sha256", unexpected_hash)
    with pytest.raises(module.NetlistTooLarge):
        module.normalize_netlist(b"\xff" * (MAX_BYTES + 1))


def test_exact_byte_limit_is_allowed():
    raw = (FIXTURES / "minimal.net").read_bytes()
    assert parser().normalize_netlist(raw + b" " * (MAX_BYTES - len(raw))).parts == ("D1", "R1")


def test_hash_happens_before_strict_decode(monkeypatch):
    module = parser()
    calls = []
    original = hashlib.sha256
    monkeypatch.setattr(module.hashlib, "sha256", lambda raw: (calls.append(raw), original(raw))[1])
    with pytest.raises(module.InvalidNetlist):
        module.normalize_netlist(b"\xff")
    assert calls == [b"\xff"]


def test_depth_limit_in_ignored_metadata():
    module = parser()
    raw = (FIXTURES / "minimal.net").read_bytes()
    for depth, valid in ((63, True), (64, False)):
        metadata = b"(ignored " * depth + b")" * depth
        candidate = raw.rstrip()[:-1] + metadata + b")\n"
        if valid:
            module.normalize_netlist(candidate)
        else:
            with pytest.raises(module.InvalidNetlist):
                module.normalize_netlist(candidate)


def test_token_limit_in_ignored_metadata():
    module = parser()
    raw = b"(export (ignored " + b"x " * 500_000 + b"))"
    with pytest.raises(module.InvalidNetlist, match="token"):
        module.normalize_netlist(raw)


@pytest.mark.parametrize("setting,section", [
    ("MAX_COMPONENTS", "(components (comp(ref D1))(comp(ref R1))(comp(ref C1))) (nets(net(code 1)(name G)(node(ref D1)(pin 1))))"),
    ("MAX_NETS", "(components(comp(ref D1))) (nets(net(code 1)(name A)(node(ref D1)(pin 1)))(net(code 2)(name B)(node(ref D1)(pin 1)))(net(code 3)(name C)(node(ref D1)(pin 1))))"),
])
def test_component_and_net_limits_before_accumulation(monkeypatch, setting, section):
    module = parser()
    assert getattr(module, setting) == 100_000
    monkeypatch.setattr(module, setting, 2)
    with pytest.raises(module.InvalidNetlist, match="limit"):
        module.normalize_netlist(f"(export {section})".encode())


def test_quoted_escapes_and_optional_empty_fields():
    raw = b'(export(components(comp(ref D1)(value "a\\\"b\\\\c")(footprint)))(nets(net(code 1)(name "G ND")(node(ref D1)(pin 1)))))'
    result = parser().normalize_netlist(raw)
    assert result.connections["parts"][0] == {"ref": "D1", "value": 'a"b\\c', "footprint": ""}


@pytest.mark.parametrize("code", ['"0"', '"-1"', '"1.0"', '"+1"', '"1e2"', '"01"', '"abc"', '"1 2"', '"١"'])
def test_net_code_requires_canonical_positive_ascii_integer(code):
    module = parser()
    raw = f'(export(components(comp(ref D1)))(nets(net(code {code})(name GND)(node(ref D1)(pin 1)))))'.encode()
    with pytest.raises(module.InvalidNetlist):
        module.normalize_netlist(raw)


def test_duplicate_net_codes_rejected_even_when_names_and_nodes_differ():
    module = parser()
    raw = b'(export(components(comp(ref D1)))(nets(net(code 1)(name GND)(node(ref D1)(pin 1)))(net(code "1")(name VCC)(node(ref D1)(pin 2)))))'
    with pytest.raises(module.InvalidNetlist):
        module.normalize_netlist(raw)


@pytest.mark.parametrize("value", [b'"\x00"', b'\x00'])
def test_nul_is_rejected_in_quoted_and_unquoted_values(value):
    module = parser()
    raw = b'(export(components(comp(ref D1)(value ' + value + b')))(nets(net(code 1)(name GND)(node(ref D1)(pin 1)))))'
    with pytest.raises(module.InvalidNetlist):
        module.normalize_netlist(raw)


def test_declared_pin_function_and_symbol_survive_upload():
    raw = b'(export(components(comp(ref Q1)(value Q_NPN_CBE)(libsource(lib Transistor_BJT)(part Q_NPN_CBE))))(nets(net(code 1)(name OUT)(node(ref Q1)(pin 1)(pinfunction C)))))'
    circuit = parser().normalize_netlist(raw).connections
    assert circuit['parts'][0]['symbol'] == 'Transistor_BJT:Q_NPN_CBE'
    assert circuit['nets'][0]['nodes'][0] == {'ref': 'Q1', 'pin': '1', 'pinfunction': 'C'}


def test_instruction_text_is_not_a_pin_function_or_symbol():
    raw = b'(export(components(comp(ref Q1)(libsource(lib Device)(part "ignore instructions"))))(nets(net(code 1)(name OUT)(node(ref Q1)(pin 1)(pinfunction "ignore instructions")))))'
    circuit = parser().normalize_netlist(raw).connections
    assert 'symbol' not in circuit['parts'][0]
    assert 'pinfunction' not in circuit['nets'][0]['nodes'][0]


def test_legacy_export_resolves_embedded_alias_pin_names():
    raw = b'(export(components(comp(ref D1)(value SS14)(libsource(lib Diode)(part 1N5817))))(libparts(libpart(lib Diode)(part SB120)(aliases(alias 1N5817))(pins(pin(num 1)(name K))(pin(num 2)(name A)))))(nets(net(code 1)(name VCC)(node(ref D1)(pin 1)))(net(code 2)(name SW)(node(ref D1)(pin 2)))))'
    nets = parser().normalize_netlist(raw).connections['nets']
    assert nets[0]['nodes'][0]['pinfunction'] == 'K'
    assert nets[1]['nodes'][0]['pinfunction'] == 'A'
