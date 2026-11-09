"""KiCad .net 업로드를 circuit_around가 읽는 연결 목록으로 바꾼다. 파일 접근 없음."""
import json
import re
from xml.etree import ElementTree as ET

MAX_BYTES = 1024 * 1024
TOKEN = re.compile(r'\s+|"(?:\\.|[^"\\])*"|[()]|[^()\s"]+')


def _sexpr(text):
    stack, roots, end, count = [], [], 0, 0
    for match in TOKEN.finditer(text):
        if match.start() != end:
            raise ValueError('넷리스트 문자열이 올바르지 않습니다.')
        end = match.end()
        token = match.group()
        if token.isspace():
            continue
        count += 1
        if count > 200000 or len(stack) > 64:
            raise ValueError('넷리스트 구조가 너무 큽니다.')
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            if not stack:
                raise ValueError('넷리스트 괄호가 올바르지 않습니다.')
            stack.pop()
        else:
            (stack[-1] if stack else roots).append(json.loads(token) if token.startswith('"') else token)
    if end != len(text) or stack or len(roots) != 1 or not isinstance(roots[0], list):
        raise ValueError('넷리스트 구조가 올바르지 않습니다.')
    return roots[0]


def _children(node, tag):
    return [x for x in node[1:] if isinstance(x, list) and x and x[0] == tag]


def _field(node, tag):
    found = _children(node, tag)
    return found[0][1] if found and len(found[0]) == 2 and isinstance(found[0][1], str) else ''


def parse_netlist(text: str) -> dict:
    """최대 1 MiB UTF-8 S-expression/XML. 잘못된 형식·참조는 ValueError."""
    if not text.strip() or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('넷리스트는 비어 있지 않은 1 MiB 이하 파일이어야 합니다.')
    try:
        if text.lstrip('\ufeff \r\n\t').startswith('<'):
            if re.search(r'<!\s*(DOCTYPE|ENTITY)', text, re.I):
                raise ValueError('XML 외부 선언은 허용하지 않습니다.')
            root = ET.fromstring(text)
            if root.tag != 'export':
                raise ValueError('KiCad export 넷리스트가 필요합니다.')
            if sum(1 for _ in root.iter()) > 50000:
                raise ValueError('넷리스트 요소가 너무 많습니다.')
            frontier = [(root, 0)]
            while frontier:
                element, depth = frontier.pop()
                if depth > 64:
                    raise ValueError('넷리스트가 너무 깊습니다.')
                frontier.extend((child, depth + 1) for child in element)
            parts = [{'ref': c.get('ref', ''), 'value': c.findtext('value', ''),
                      'footprint': c.findtext('footprint', '')} for c in root.findall('./components/comp')]
            nets = [{'name': n.get('name', ''), 'nodes': [
                {k: c.get(k, '') for k in ('ref', 'pin', 'pinfunction') if k in c.attrib}
                for c in n.findall('node')]} for n in root.findall('./nets/net')]
        else:
            root = _sexpr(text.lstrip('\ufeff'))
            if not root or root[0] != 'export':
                raise ValueError('KiCad export 넷리스트가 필요합니다.')
            sections = _children(root, 'components')
            parts = [{k: _field(c, k) for k in ('ref', 'value', 'footprint')}
                     for section in sections for c in _children(section, 'comp')]
            nets = [{'name': _field(n, 'name'), 'nodes': [
                {k: _field(c, k) for k in ('ref', 'pin', 'pinfunction') if _field(c, k)}
                for c in _children(n, 'node')]} for section in _children(root, 'nets') for n in _children(section, 'net')]
    except (ET.ParseError, json.JSONDecodeError, IndexError, TypeError) as error:
        raise ValueError('KiCad 넷리스트를 읽을 수 없습니다.') from error
    refs = [p['ref'] for p in parts]
    if not parts or not nets or len(parts) > 2000 or len(nets) > 5000 or len(set(refs)) != len(refs):
        raise ValueError('부품·넷이 없거나 중복되거나 너무 많습니다.')
    if any(not re.fullmatch(r'[A-Za-z#][A-Za-z0-9_#.$+-]{0,99}', r) for r in refs):
        raise ValueError('부품 참조명이 올바르지 않습니다.')
    names = [n['name'] for n in nets]
    if len(set(names)) != len(names) or any(not n or len(n) > 500 for n in names):
        raise ValueError('넷 이름이 올바르지 않습니다.')
    known = set(refs)
    if sum(len(n['nodes']) for n in nets) > 20000 or any(
        c.get('ref') not in known or not c.get('pin') or len(c['pin']) > 100
        for n in nets for c in n['nodes']
    ):
        raise ValueError('넷의 부품·핀 참조가 올바르지 않습니다.')
    return {'components': parts, 'nets': nets}
