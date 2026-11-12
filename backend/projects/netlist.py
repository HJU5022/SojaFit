"""KiCad export의 연결 정보만 제한된 메모리에서 읽는다. 원본은 결과에 남기지 않는다."""
import hashlib
import re
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping

MAX_BYTES = 5 * 1024 * 1024
MAX_DEPTH = 64
MAX_TOKENS = 500_000
MAX_COMPONENTS = 100_000
MAX_NETS = 100_000
PARSER_VERSION = "kicad-export-v2"


class InvalidNetlist(ValueError):
    """연결 정보가 없거나 제한된 KiCad export 문법이 아니다."""


class NetlistTooLarge(InvalidNetlist):
    """원본 바이트 상한 초과."""


@dataclass(frozen=True, slots=True)
class NormalizedCircuit:
    connections: Mapping
    source_sha256: str
    parts: tuple[str, ...]


def _tokens(text):
    index, count = 0, 0
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        count += 1
        if count > MAX_TOKENS:
            raise InvalidNetlist("token limit exceeded")
        char = text[index]
        index += 1
        if char in "()":
            yield char, None
            continue
        if char == '"':
            value = []
            while index < len(text) and text[index] != '"':
                char = text[index]
                index += 1
                if char == "\\":
                    if index == len(text) or text[index] not in '\\"nrt':
                        raise InvalidNetlist("invalid escape")
                    char = {"n": "\n", "r": "\r", "t": "\t"}.get(text[index], text[index])
                    index += 1
                value.append(char)
            if index == len(text):
                raise InvalidNetlist("unterminated string")
            index += 1
            if index < len(text) and not text[index].isspace() and text[index] not in "()":
                raise InvalidNetlist("invalid string delimiter")
            yield "atom", "".join(value)
        else:
            start = index - 1
            while index < len(text) and not text[index].isspace() and text[index] not in "()":
                if text[index] == '"' or text[index] == "\x00":
                    raise InvalidNetlist("invalid atom")
                index += 1
            if "\x00" in text[start:index]:
                raise InvalidNetlist("invalid atom")
            yield "atom", text[start:index]


def _read_export(text):
    tokens = iter(_tokens(text))
    counts = {"comp": 0, "net": 0}
    keep = {
        ("export",), ("export", "components"), ("export", "components", "comp"),
        ("export", "nets"), ("export", "nets", "net"), ("export", "nets", "net", "node"),
    }
    keep.update({("export", "libparts"), ("export", "libparts", "libpart")})
    for name in ("lib", "part", "aliases", "pins"):
        keep.add(("export", "libparts", "libpart", name))
    keep.add(("export", "libparts", "libpart", "aliases", "alias"))
    keep.add(("export", "libparts", "libpart", "pins", "pin"))
    for name in ("num", "name"):
        keep.add(("export", "libparts", "libpart", "pins", "pin", name))
    for name in ("ref", "value", "footprint", "libsource"):
        keep.add(("export", "components", "comp", name))
    for name in ("lib", "part"):
        keep.add(("export", "components", "comp", "libsource", name))
    for name in ("code", "name"):
        keep.add(("export", "nets", "net", name))
    for name in ("ref", "pin", "pinfunction"):
        keep.add(("export", "nets", "net", "node", name))

    def node(parent):
        if len(parent) >= MAX_DEPTH:
            raise InvalidNetlist("depth limit exceeded")
        kind, tag = next(tokens, (None, None))
        if kind != "atom" or not tag:
            raise InvalidNetlist("expected node name")
        path = (*parent, tag)
        if path in (("export", "components", "comp"), ("export", "nets", "net")):
            counts[tag] += 1
            if counts[tag] > (MAX_COMPONENTS if tag == "comp" else MAX_NETS):
                raise InvalidNetlist("record limit exceeded")
        values = []
        for kind, value in tokens:
            if kind == ")":
                return (tag, tuple(values)) if path in keep else None
            if kind == "(":
                value = node(path)
            if path in keep and value is not None:
                values.append(value)
        raise InvalidNetlist("unbalanced structure")

    if next(tokens, (None, None))[0] != "(":
        raise InvalidNetlist("expected export")
    root = node(())
    if root is None or root[0] != "export" or next(tokens, None) is not None:
        raise InvalidNetlist("expected one export")
    return root


def _children(node, tag):
    return [item for item in node[1] if isinstance(item, tuple) and item[0] == tag]


def _field(node, tag, required=False):
    matches = _children(node, tag)
    if not matches and not required:
        return ""
    if len(matches) != 1:
        raise InvalidNetlist("missing or duplicate field")
    values = matches[0][1]
    if not values and not required:
        return ""
    if len(values) != 1 or not isinstance(values[0], str) or (required and not values[0]):
        raise InvalidNetlist("expected scalar field")
    return values[0]


def _declared_symbol_pins(root):
    """Read pin names from this export's embedded library, including explicit aliases."""
    symbols = {}
    for library in _children(root, "libparts"):
        for symbol in _children(library, "libpart"):
            lib, part = _field(symbol, "lib"), _field(symbol, "part")
            aliases = [part]
            for group in _children(symbol, "aliases"):
                for alias in _children(group, "alias"):
                    if len(alias[1]) == 1 and isinstance(alias[1][0], str):
                        aliases.append(alias[1][0])
            pins = {}
            for group in _children(symbol, "pins"):
                for pin in _children(group, "pin"):
                    number, name = _field(pin, "num"), _field(pin, "name")
                    if number and name and re.fullmatch(r"[A-Za-z0-9_~{}.+/-]{1,64}", name):
                        pins[number] = name
            for alias in aliases:
                key = f"{lib}:{alias}"
                if key in symbols and symbols[key] != pins:
                    symbols[key] = {}
                else:
                    symbols[key] = pins
    return symbols


def normalize_netlist(raw: bytes) -> NormalizedCircuit:
    if len(raw) > MAX_BYTES:
        raise NetlistTooLarge("byte limit exceeded")
    source_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise InvalidNetlist("expected UTF-8") from None
    if "\x00" in text:
        raise InvalidNetlist("NUL is not allowed")
    root = _read_export(text)
    components, net_sections = _children(root, "components"), _children(root, "nets")
    if len(components) != 1 or len(net_sections) != 1:
        raise InvalidNetlist("missing or duplicate components/nets")
    parts = []
    for comp in _children(components[0], "comp"):
        fields = {name: _field(comp, name, name == "ref") for name in ("ref", "value", "footprint")}
        source = _children(comp, "libsource")
        if len(source) == 1:
            lib, symbol = _field(source[0], "lib"), _field(source[0], "part")
            if lib and symbol and all(re.fullmatch(r"[A-Za-z0-9_.+/-]{1,100}", x) for x in (lib, symbol)):
                fields["symbol"] = f"{lib}:{symbol}"
        parts.append(MappingProxyType(fields))
    parts = tuple(parts)
    refs = tuple(part["ref"] for part in parts)
    if not refs or len(set(refs)) != len(refs):
        raise InvalidNetlist("missing or duplicate components")
    known_refs = set(refs)
    part_symbols = {part["ref"]: part.get("symbol", "") for part in parts}
    library_pins = _declared_symbol_pins(root)
    nets = []
    codes = set()
    for net in _children(net_sections[0], "net"):
        code = _field(net, "code", True)
        if not code.isascii() or not code.isdecimal() or code.startswith("0") or code in codes:
            raise InvalidNetlist("expected unique positive integer net code")
        codes.add(code)
        nodes = []
        for item in _children(net, "node"):
            fields = {name: _field(item, name, True) for name in ("ref", "pin")}
            function = _field(item, "pinfunction") or library_pins.get(part_symbols.get(fields["ref"]), {}).get(fields["pin"], "")
            if function and re.fullmatch(r"[A-Za-z0-9_~{}.+/-]{1,64}", function):
                fields["pinfunction"] = function
            nodes.append(MappingProxyType(fields))
        nodes = tuple(nodes)
        if not nodes or any(item["ref"] not in known_refs for item in nodes):
            raise InvalidNetlist("missing or unknown nodes")
        nets.append(MappingProxyType({"code": code, "name": _field(net, "name", True), "nodes": nodes}))
    if not nets:
        raise InvalidNetlist("missing nets")
    return NormalizedCircuit(MappingProxyType({"parts": parts, "nets": tuple(nets)}), source_sha256, refs)
