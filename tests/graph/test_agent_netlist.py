"""사용자 KiCad 업로드의 파싱·자원 제한·참조 검증."""
from pathlib import Path

import pytest

from backend.graph.netlist import parse_netlist


NET = '(export (version "E") (components (comp (ref "D1") (value "SS34") (footprint "SMA"))) (nets (net (code "1") (name "VCC") (node (ref "D1") (pin "1")))))'


def test_kicad_sexpression_and_xml_have_the_same_connections():
    xml = '<export><components><comp ref="D1"><value>SS34</value><footprint>SMA</footprint></comp></components><nets><net code="1" name="VCC"><node ref="D1" pin="1"/></net></nets></export>'
    parsed = parse_netlist(NET)
    assert parsed == parse_netlist(xml)
    assert parsed['components'] == [{'ref': 'D1', 'value': 'SS34', 'footprint': 'SMA'}]
    assert parsed['nets'][0]['nodes'] == [{'ref': 'D1', 'pin': '1'}]


def test_existing_public_netlist_has_target_diode():
    net = Path('data/circuits/collected/samples/breadboard_supply/converted/circuit.net').read_text(encoding='utf-8')
    parsed = parse_netlist(net)
    assert any(p['ref'] == 'D1' for p in parsed['components'])
    assert parsed['nets']


@pytest.mark.parametrize('bad', ['', '(export', '(export))', NET + 'junk', NET.replace('SS34', '"'),
    NET.replace('(ref "D1") (pin', '(ref "D2") (pin'),
    NET.replace('(components', '(components (comp (ref "D1") (value "x"))'),
    '<!DOCTYPE export [<!ENTITY a "x">]><export/>', '(a ' * 70 + ')' * 70, 'x' * (1024 * 1024 + 1), NET.replace('SS34', 'SS\x0034')])
def test_invalid_or_excessive_netlists_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_netlist(bad)
