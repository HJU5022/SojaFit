"""제조사 원문 표의 페이지·행·열을 보존한 인용 후보. PDF 파서는 별도 프로세스에서 실행한다."""
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


# 제품·커뮤니티 글과 사용자 업로드 주소는 다운로드 대상에서 제외한다.
PDF_PATHS = {
    'www.vishay.com': '/docs/',
    'www.ti.com': '/lit/ds/symlink/',
    'www.onsemi.com': '/pdf/datasheet/',
    'assets.nexperia.com': '/documents/data-sheet/',
    'www.st.com': '/resource/en/datasheet/',
    'www.analog.com': '/media/en/technical-documentation/data-sheets/',
}
MAX_BYTES = 12 * 1024 * 1024
MAX_PAGES = 32
MAX_ROWS = 3
NUMBER = re.compile(r'[+−–-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*[%])?')
CAPTION = re.compile(r'^(?:Table\s+\d+[. :–-]|\d+(?:\.\d+)+\s+|.*(?:RATINGS|CHARACTERISTICS|OPERATING CONDITIONS)\b)', re.I)


def official_pdf(url):
    if not isinstance(url, str) or len(url) > 2048 or not url.isascii() or '\\' in url or any(c.isspace() or ord(c) < 32 for c in url):
        return ''
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if parsed.scheme != 'https' or parsed.netloc.lower() != host or host not in PDF_PATHS:
            return ''
        remaining = parsed.path[len(PDF_PATHS[host]):]
        filename = r'\d+/[\w.-]+\.pdf' if host == 'www.vishay.com' else r'[\w.-]+\.pdf'
        if parsed.path.lower().startswith(PDF_PATHS[host]) and re.fullmatch(filename, remaining, re.I | re.ASCII):
            return f'https://{host}{parsed.path}'
    except ValueError:
        pass
    return ''


def clean(text):
    return ' '.join((text or '').split())


def _header(row):
    cells = [clean(c).upper() for c in row]
    return any(c in ('UNIT', 'UNITS') for c in cells) and any(c in ('PARAMETER', 'SYMBOL', 'MIN', 'TYP', 'MAX') for c in cells)


def _caption(page, table, rows, idx):
    for row in reversed(rows[:idx]):
        nonempty = [clean(c) for c in row if clean(c)]
        if len(nonempty) == 1 and CAPTION.match(nonempty[0]):
            return nonempty[0][:220]
    x0, top, x1, _ = table.bbox
    if top <= 1:
        return ''
    before = page.crop((x0, max(page.bbox[1], top - 60), x1, top)).extract_text(x_tolerance=1) or ''
    lines = before.splitlines()
    for i in reversed(range(len(lines))):
        if CAPTION.match(lines[i].strip()):
            return clean(' '.join(lines[i:]))[:220]
    return ''


def _read_table(page, table, parts, single, terms):
    rows = table.extract(x_tolerance=1)
    index = next((i for i, row in enumerate(rows[:4]) if _header(row)), None)
    if index is None:
        return
    caption = _caption(page, table, rows, index)
    if not caption:
        return
    header = [clean(c).upper() for c in rows[index]]
    matches = [p for p in parts if p in header]
    if not matches and not single:
        return
    label_index = header.index('PARAMETER') if 'PARAMETER' in header else 0
    unit_index = next(i for i, name in enumerate(header) if name in ('UNIT', 'UNITS'))
    for row_index, raw in enumerate(rows[index + 1:], start=index + 1):
        row = [clean(c) for c in raw]
        label, unit = row[label_index], row[unit_index]
        if not label or not unit or len(label) > 180 or len(unit) > 24:
            continue
        symbol = row[header.index('SYMBOL')] if 'SYMBOL' in header else ''
        normalized = re.sub(r'[^a-z0-9]', '', label.lower())
        normalized_symbol = re.sub(r'[^a-z0-9]', '', symbol.lower())
        hits = sum(word == normalized_symbol or (len(word) > 2 and word in normalized) for word in terms)
        if not hits:
            continue
        conditions = ' '.join(row[i] for i, name in enumerate(header) if 'CONDITION' in name and row[i])
        for part in matches or [single]:
            if matches:
                value = row[header.index(part)]
                if not NUMBER.fullmatch(value):
                    continue
                values = [f'{part} = {value} {unit}']
            else:
                # Some PDF tables have no vertical rules in their data rows. Use the
                # actual header column bounds, never the order of two merged numbers.
                y = table.rows[row_index].bbox
                values = []
                for i, name in enumerate(header):
                    if name not in ('MIN', 'TYP', 'MAX', 'VALUE'):
                        continue
                    cell = table.rows[index].cells[i]
                    if cell is None:
                        continue
                    text = clean(page.crop((cell[0], y[1], cell[2], y[3])).extract_text(x_tolerance=1))
                    if text and not NUMBER.fullmatch(text):
                        values = []
                        break
                    if text:
                        values.append(f'{name} = {text} {unit}')
                if not values:
                    continue
            content = ' | '.join(filter(None, (part, caption, label, symbol, conditions, *values)))
            yield hits, {'page': page.page_number, 'table': caption, 'row': label,
                         'doc_parts': [part], 'content': content}


def extract(raw, url, parts, terms):
    import pdfplumber
    if not official_pdf(url) or not raw.startswith(b'%PDF-') or len(raw) > MAX_BYTES:
        return []
    parts = [p.upper() for p in parts]
    found = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        slug = Path(urlsplit(url).path).stem.upper()
        def named_sheet(page):
            heading = page.crop((0, 0, page.width, min(page.height, 165))).extract_text(x_tolerance=1) or ''
            return slug in {line.strip().upper() for line in heading.splitlines()}

        single = slug if (urlsplit(url).hostname == 'www.ti.com' and slug in parts and named_sheet(pdf.pages[0])) else ''
        for page in pdf.pages[:MAX_PAGES]:
            page_part = single if single and named_sheet(page) else ''
            for table in page.find_tables():
                found.extend(_read_table(page, table, parts, page_part, terms))
            page.close()
    return [row for _, row in sorted(found, key=lambda pair: -pair[0])[:MAX_ROWS]]


def verified_rows(raw, url, parts, terms):
    """Network bytes are never written to disk. Limit time and (Linux) CPU/address space."""
    worker = Path(__file__).resolve()
    try:
        result = subprocess.run([sys.executable, '-I', str(worker), url, json.dumps(parts), json.dumps(terms)],
                                input=raw, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=12, check=True,
                                env={k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'PATH', 'TMP', 'TEMP', 'LANG')
                                     if k in os.environ})
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, OSError, ValueError):
        return []


if __name__ == '__main__':
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    print(json.dumps(extract(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1],
                             json.loads(sys.argv[2]), json.loads(sys.argv[3]))))
