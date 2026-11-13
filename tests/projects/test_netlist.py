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
