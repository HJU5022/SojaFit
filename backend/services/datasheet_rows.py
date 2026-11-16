"""제조사 원문 표의 페이지·행·열을 보존한 인용 후보. PDF 파서는 별도 프로세스에서 실행한다."""
import io
import base64
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlsplit, urlunsplit

LOGGER = logging.getLogger(__name__)

# 제품·커뮤니티 글과 사용자 업로드 주소는 다운로드 대상에서 제외한다.
PDF_PATHS = {
    'www.vishay.com': '/docs/',
    'www.ti.com': '/lit/ds/symlink/',
    'www.onsemi.com': '/pdf/datasheet/',
    'assets.nexperia.com': '/documents/data-sheet/',
    'www.st.com': '/resource/en/datasheet/',
    'www.analog.com': '/media/en/technical-documentation/data-sheets/',
}
GRADE2_PDF_PATHS = {
    'services.taiwansemi.com': '/storage/resources/datasheet/',
    'www.infineon.com': '/assets/row/public/documents/',
    'www.vishay.com': '/docs/',
    'www.ti.com': '/lit/ds/symlink/',
    'www.onsemi.com': '/pdf/datasheet/',
    'www.st.com': '/resource/en/datasheet/',
    'www.analog.com': '/media/en/technical-documentation/data-sheets/',
}
_GRADE2_EXCLUDED = re.compile(r'(?:application[-_ ]?note|app[-_ ]?note|reference[-_ ]?manual|user[-_ ]?guide)', re.I)
MAX_BYTES = 12 * 1024 * 1024
MAX_PAGES = 32
MAX_ROWS = 3
NUMBER = re.compile(r'[+−–-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*[%])?')
CAPTION = re.compile(r'^(?:Table\s+\d+[. :–-]|\d+(?:\.\d+)+\s+|.*(?:RATINGS|CHARACTERISTICS|ELECTRICAL SPECIFICATIONS|OPERATING CONDITIONS)\b)', re.I)
FIGURE_CAPTION = re.compile(r'(?im)^Fig\.?\s*\d+\b[^\n]*Reverse Recovery Time[^\n]*')


def _pdf_paths(grade):
    return GRADE2_PDF_PATHS if grade == 2 else PDF_PATHS


def official_pdf(url, *, grade=None):
    if not isinstance(url, str) or len(url) > 2048 or '\\' in url or any(ord(c) < 32 for c in url):
        return ''
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        paths = _pdf_paths(grade)
        if (parsed.scheme != 'https' or parsed.netloc.lower() != host or host not in paths
                or parsed.fragment):
            return ''
        query = ''
        if parsed.query:
            # Infineon document links commonly carry one opaque CMS locator.
            # Keep only the two documented locator names; never accept a
            # duplicate/unknown parameter or arbitrary query text.
            if not (grade == 2 and host == 'www.infineon.com'):
                return ''
            pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
            if len(pairs) != 1 or pairs[0][0] not in {'fileId', 'folderId'}:
                return ''
            if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', pairs[0][1]):
                return ''
            query = quote(pairs[0][0], safe='') + '=' + quote(pairs[0][1], safe='')
        decoded_path = unquote(parsed.path)
        prefix = paths[host]
        remaining = decoded_path[len(prefix):] if decoded_path.lower().startswith(prefix.lower()) else ''
        if host == 'www.vishay.com':
            filename = r'\d+/[\w .()+-]+\.pdf'
        elif host == 'www.infineon.com':
            filename = r'\d+/\d+/[\w .()+-]+\.pdf'
        else:
            filename = r'[\w .()+-]+\.pdf'
        if grade == 2 and host == 'www.infineon.com':
            if not re.search(r'(?:^|[-_ ])(?:datasheet|ds)(?=[-_ .])', remaining.rsplit('/', 1)[-1], re.I):
                return ''
        if (remaining and not (grade == 2 and _GRADE2_EXCLUDED.search(remaining))
                and re.fullmatch(filename, remaining, re.I | re.ASCII)):
            return urlunsplit(('https', host, quote(decoded_path, safe='/%()+-._'), query, ''))
    except ValueError:
        pass
    return ''


def grade2_pdf(url):
    """Return a canonical manufacturer URL eligible for evidence grade 2."""
    return official_pdf(url, grade=2)


def clean(text):
    return ' '.join((text or '').split())


def _language_for_pages(texts):
    """Use the trusted document-language contract and fail closed if unavailable."""
    try:
        repo_root = Path(__file__).resolve().parents[2]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from backend.services.document_language import language_for_pages
        return language_for_pages(texts)
    except (ImportError, AttributeError):
        return None


def _text_rows(page, parts, terms):
    """Extract an unruled text row using label/value/unit geometry, not part values."""
    text = page.extract_text(x_tolerance=1) or ''
    if not text or not any(_strict_part_mention(text, part) for part in parts):
        return []
    lines = text.splitlines()
    rows = []
    term_set = {re.sub(r'[^a-z0-9]', '', str(term).lower()) for term in terms}
    for index, line in enumerate(lines):
        normalized = clean(line)
        match = re.search(r'(?P<label>[A-Za-z][A-Za-z _/-]{3,})(?:\s+|=)+(?P<value>[+−–-]?(?:\d+(?:\.\d+)?|\.\d+))\s*(?P<unit>mA|µA|uA|V|mV|A|Ω|ohm|%)\b', normalized, re.I)
        if not match:
            continue
        label = clean(match.group('label'))
        label_words = set(re.findall(r'[a-z0-9]+', label.lower()))
        if not term_set or not any(term in label_words or term in re.sub(r'[^a-z0-9]', '', label.lower()) for term in term_set):
            continue
        bbox = None
        try:
            hits = page.search(re.escape(normalized), regex=True, return_chars=False)
            if hits:
                hit = hits[0]
                bbox = [hit.get(key) for key in ('x0', 'top', 'x1', 'bottom')]
        except (AttributeError, TypeError, ValueError):
            pass
        caption = next((clean(previous) for previous in reversed(lines[:index])
                        if CAPTION.match(clean(previous))), '')
        if not caption:
            continue
        rows.append((1, {'page': page.page_number, 'table': caption,
                         'row': label, 'doc_parts': [parts[0]],
                         'content': f'{parts[0]} | {caption} | {label} | {match.group("value")} {match.group("unit")}',
                         'cells': [('VALUE', match.group('value'))],
                         'unit': match.group('unit'), 'conditions': '', 'symbol': '',
                         **({'bbox': bbox} if bbox else {})}))
    return rows


def _covered_part(parts, page_texts):
    """Require exact part evidence in a title or ordering/type table, not prose."""
    scope = re.compile(r'(?:ordering(?:\s+information)?|order\s+code|type\s+number|device\s+specific|part\s+number)', re.I)
    for index, text in enumerate(page_texts):
        for part in parts:
            if not _strict_part_mention(text, part):
                continue
            if scope.search(text):
                return part
            if index == 0:
                title_lines = [line.strip() for line in text.splitlines()[:8]]
                part_positions = [position for position, line in enumerate(title_lines)
                                  if _strict_part_mention(line, part)]
                nearby_title = [title_lines[line_position]
                                for part_position in part_positions
                                for line_position in range(max(0, part_position - 1), min(len(title_lines), part_position + 3))]
                if any(re.search(r'\b(?:datasheet|reference|diode|voltage|regulator|micropower)\b', line, re.I)
                       and not re.search(r'\bdevice\b', line, re.I) for line in nearby_title):
                    return part
    return ''


def _header(row):
    cells = [clean(c).upper() for c in row]
    return any(c in ('UNIT', 'UNITS') for c in cells) and any(c in ('PARAMETER', 'SYMBOL', 'MIN', 'TYP', 'MAX') for c in cells)


def _caption(page, table, rows, idx):
    for row in reversed(rows[:idx]):
        nonempty = [clean(c) for c in row if clean(c)]
        if len(nonempty) == 1 and CAPTION.match(nonempty[0]):
            return nonempty[0][:220]
    # Some PDFs split the first glyph of a caption across a cell (e.g.
    # ``E`` + ``LECTRICAL SPECIFICATIONS``). Rejoin that layout before the
    # geometric fallback so row-oriented tables remain eligible.
    above = clean(' '.join(clean(c) for row in rows[:idx] for c in row if clean(c)))
    above = re.sub(r'\bE\s+LECTRICAL\b', 'ELECTRICAL', above, flags=re.I)
    if CAPTION.match(above):
        return above[:220]
    x0, top, x1, _ = table.bbox
    if top <= 1:
        return ''
    before = page.crop((x0, max(page.bbox[1], top - 60), x1, top)).extract_text(x_tolerance=1) or ''
    lines = before.splitlines()
    for i in reversed(range(len(lines))):
        if CAPTION.match(lines[i].strip()):
            return clean(' '.join(lines[i:]))[:220]
    return ''


def _merged_cell_text(page, table, row_index, column_index):
    """Read a vertically-spanning cell whose physical bbox covers this row."""
    row_box = table.rows[row_index].bbox
    center = (row_box[1] + row_box[3]) / 2
    current = table.rows[row_index].cells[column_index]
    candidates = [current] if current is not None else []
    if current is None:
        for previous in reversed(table.rows[:row_index]):
            cell = previous.cells[column_index]
            if cell is not None and cell[1] <= center <= cell[3]:
                candidates.append(cell)
                break
    for cell in candidates:
        text = clean(page.crop(cell).extract_text(x_tolerance=1, y_tolerance=5))
        if text:
            return text
    return ''


def _row_has_part(row_text, part):
    """Match a data-row ordering code without accepting a suffixed sibling."""
    return bool(re.search(r'(?<![A-Z0-9])' + re.escape(part.upper()) + r'(?![A-Z0-9])', row_text.upper()))


def _strict_part_mention(text, part):
    """Match an exact order identity, including punctuation suffix boundaries."""
    return bool(re.search(r'(?<![A-Z0-9])' + re.escape(part.upper()) + r'(?![A-Z0-9._+\-/])', text.upper()))


def _is_vishay_vrrm_symbol(symbol):
    """Accept only the documented VRRM symbol or its PDF subscript layout."""
    raw = str(symbol or '').upper()
    # pdfplumber can expose Vishay's subscripted ``VRRM = VRWM = VR`` as
    # ``V = V = V RRM RWM R``. Keep this one known layout, not arbitrary prose.
    return re.sub(r'\s+', '', raw) in {'VRRM', 'VRRM=VRWM=VR', 'V=V=VRRMRWMR'}


def _read_table(page, table, parts, single, terms):
    rows = table.extract(x_tolerance=1, y_tolerance=5)
    index = next((i for i, row in enumerate(rows[:4]) if _header(row)), None)
    if index is None:
        return
    caption = _caption(page, table, rows, index)
    if not caption:
        return
    header = [clean(c).upper() for c in rows[index]]
    # Manufacturer PDFs may split a product token over lines (e.g. SS34/LW).
    # Remove only layout whitespace; do not treat SS34 as SS34LW.
    compact = [re.sub(r'\s+', '', c) for c in header]
    row_product_mode = any(any(p in re.sub(r'\s+', '', clean(cell)) for cell in row if cell) for row in rows[index + 1:] for p in parts)
    matches = [p for p in parts if p in compact]
    if not matches and not single and not row_product_mode:
        return
    label_index = header.index('PARAMETER') if 'PARAMETER' in header else 0
    unit_index = next(i for i, name in enumerate(header) if name in ('UNIT', 'UNITS'))
    for row_index, raw in enumerate(rows[index + 1:], start=index + 1):
        row = [clean(c) for c in raw]
        label = row[label_index] or _merged_cell_text(page, table, row_index, label_index)
        unit = row[unit_index] or _merged_cell_text(page, table, row_index, unit_index)
        if not label or not unit or len(label) > 180 or len(unit) > 24:
            continue
        symbol_index = header.index('SYMBOL') if 'SYMBOL' in header else None
        symbol = (row[symbol_index] if symbol_index is not None else '') or (
            _merged_cell_text(page, table, row_index, symbol_index) if symbol_index is not None else '')
        normalized = re.sub(r'[^a-z0-9]', '', label.lower())
        normalized_symbol = re.sub(r'[^a-z0-9]', '', symbol.lower())
        hits = sum(word == normalized_symbol or (len(word) > 2 and word in normalized) for word in terms)
        if not hits:
            continue
        condition_indices = [i for i, name in enumerate(header) if 'CONDITION' in name]
        conditions = ' '.join(row[i] for i in condition_indices if row[i])
        if not conditions:
            conditions = ' '.join(filter(None, (_merged_cell_text(page, table, row_index, i) for i in condition_indices)))
        row_text = clean(' '.join(row)).upper()
        row_matches = [p for p in parts if _row_has_part(row_text, p)] if row_product_mode else []
        if row_product_mode and not row_matches:
            continue
        for part in row_matches or matches or [single]:
            if matches:
                if compact.count(part) != 1:
                    continue
                column = compact.index(part)
                value = row[column]
                if not NUMBER.fullmatch(value):
                    continue
                bounds = table.rows[row_index].cells[column]
                if bounds is None or clean(page.crop(bounds).extract_text(x_tolerance=1)) != value:
                    continue
                cells = [(part, value)]
            elif row_product_mode:
                cells = []
                for i, name in enumerate(header):
                    if name not in ('MIN', 'TYP', 'MAX', 'VALUE'):
                        continue
                    value = row[i] if i < len(row) else ''
                    if not value:
                        continue
                    bounds = table.rows[row_index].cells[i]
                    if bounds is None:
                        continue
                    observed = clean(page.crop(bounds).extract_text(x_tolerance=1, y_tolerance=5))
                    if observed != value or not NUMBER.fullmatch(value):
                        continue
                    cells.append((name, value))
                if not cells:
                    continue
            else:
                # Some PDF tables have no vertical rules in their data rows. Use the
                # actual header column bounds, never the order of two merged numbers.
                y = table.rows[row_index].bbox
                cells = []
                for i, name in enumerate(header):
                    if name not in ('MIN', 'TYP', 'MAX', 'VALUE'):
                        continue
                    cell = table.rows[index].cells[i]
                    if cell is None:
                        continue
                    text = clean(page.crop((cell[0], y[1], cell[2], y[3])).extract_text(x_tolerance=1))
                    if text and not NUMBER.fullmatch(text):
                        cells = []
                        break
                    if text:
                        cells.append((name, text))
                if not cells:
                    continue
            values = [f'{name} = {value} {unit}' for name, value in cells]
            content = ' | '.join(filter(None, (part, caption, label, symbol, conditions, *values)))
            yield hits, {'page': page.page_number, 'table': caption, 'row': label,
                         'doc_parts': [part], 'content': content, 'cells': cells,
                         'unit': unit, 'conditions': conditions, 'symbol': symbol,
                         'bbox': list(table.rows[row_index].bbox)}


def _infineon_reverse_voltage(page, parts, terms, applicable_parts):
    """Extract only the explicit BAT54-family reverse-voltage row."""
    terms = set(terms)
    # A VRRM question may use either the bare symbol or the full natural
    # language phrase. This fallback is reached only after the table parser
    # found no exact VRRM row; the returned row remains marked as VR.
    if 'vrrm' in terms:
        terms.update(('reverse', 'voltage'))
        terms.difference_update(('repetitive', 'peak', 'breakdown'))
    elif (not {'reverse', 'voltage'} <= terms
          or terms & {'repetitive', 'peak', 'breakdown'}):
        return []
    text = page.extract_text(x_tolerance=1) or ''
    caption = re.search(r'(?im)^Maximum Ratings\b[^\n]*', text)
    if not caption:
        return []
    body = text[caption.end():]
    row = re.search(r'(?im)^Diode reverse voltage +V +([0-9]+(?:\.[0-9]+)?) +V\s*\nR[ \t]*$', body)
    if not row:
        return []
    matched = [p for p in parts if p in applicable_parts]
    if not matched:
        return []
    label = 'Diode reverse voltage'
    value = row.group(1)
    table_name = clean(caption.group(0))
    # The PDF table has no Unit column, so cross-check the value using the
    # actual Symbol/Value cells before accepting the text row.
    cell_value = None
    for table in page.find_tables():
        rows = table.extract(x_tolerance=1)
        if not rows or [clean(c).upper() for c in rows[0][:2]] != ['SYMBOL', 'VALUE']:
            continue
        for index, values in enumerate(rows[1:], start=1):
            if len(values) >= 2 and re.sub(r'\s+', '', clean(values[0])).upper() == 'VR' and clean(values[1]) == row.group(1):
                cells = table.rows[index].cells
                if len(cells) >= 2 and cells[1] is not None:
                    bbox = table.rows[index].bbox
                    observed = clean(page.crop((cells[1][0], bbox[1], cells[1][2], bbox[3])).extract_text(x_tolerance=1))
                    if observed == row.group(1):
                        cell_value = row.group(1)
                break
    if cell_value is None:
        return []
    requested_symbol = 'VRRM' if 'vrrm' in set(terms) else None
    return [{'page': page.page_number, 'table': table_name, 'row': label,
             'doc_parts': [part], 'content': f'{part} | {table_name} | {label} | {part} = {value} V',
             'cells': [(part, value)], 'unit': 'V', 'conditions': '', 'symbol': 'V_R',
             **({'requested_symbol': requested_symbol} if requested_symbol else {})} for part in matched]


def _figure_png(page, caption):
    """Encode the largest raster figure on a page without writing it to disk."""
    images = list(page.images)
    # A page can contain a logo and a figure.  Prefer the first image whose
    # bounding box starts below the actual caption; without a caption bbox,
    # refuse rather than risk attaching an unrelated image.
    try:
        matches = page.search(re.escape(caption), regex=True, return_chars=False)
    except (AttributeError, TypeError, ValueError):
        return None
    if not matches:
        return None
    caption_bottom = max(item.get('bottom', 0) for item in matches)
    below = [image for image in images if image.get('top', 0) >= caption_bottom]
    if not below:
        return None
    images = sorted(below, key=lambda image: (image.get('top', 0) - caption_bottom,
                                               -image.get('width', 0) * image.get('height', 0)))
    if not images:
        return None
    image = images[0]
    width, height = image.get('srcsize') or (0, 0)
    if (not width or not height or width > 8192 or height > 8192 or width * height > 16_000_000):
        return None
    raw = image['stream'].get_data()
    if not width or not height or len(raw) not in (width * height, width * height * 3, width * height * 4):
        return None
    from PIL import Image
    mode = 'L' if len(raw) == width * height else ('RGB' if len(raw) == width * height * 3 else 'RGBA')
    picture = Image.frombytes(mode, (width, height), raw).convert('RGB')
    picture.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    while True:
        output = io.BytesIO()
        picture.save(output, format='PNG', optimize=True)
        if output.tell() <= 512 * 1024:
            break
        if min(picture.size) <= 256:
            return None
        picture = picture.resize((max(1, int(picture.width * .8)), max(1, int(picture.height * .8))), Image.Resampling.LANCZOS)
    return {'page': page.page_number, 'caption': clean(caption),
            'image_base64': base64.b64encode(output.getvalue()).decode('ascii')}


def extract(raw, url, parts, terms, *, grade=None):
    import pdfplumber
    if not official_pdf(url, grade=grade) or not raw.startswith(b'%PDF-') or len(raw) > MAX_BYTES:
        return []
    parts = [p.upper() for p in parts]
    found = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        all_pages = list(pdf.pages)
        all_texts = [page.extract_text(x_tolerance=1) or '' for page in all_pages]
        if grade == 2 and _language_for_pages(all_texts) not in {'en', 'ko', 'en-ko'}:
            return []
        pages = all_pages[:MAX_PAGES]
        slug = Path(urlsplit(url).path).stem.upper()
        def named_sheet(page):
            heading = page.crop((0, 0, page.width, min(page.height, 165))).extract_text(x_tolerance=1) or ''
            return slug in {line.strip().upper() for line in heading.splitlines()}

        host = urlsplit(url).hostname
        document_part = _covered_part(parts, all_texts) if grade == 2 else ''
        # A family PDF is allowed to answer a single part only when its first
        # page names that exact part. This is used by TI and Vishay PDFs whose
        # filename is the product identity; never infer a related suffix.
        single = slug if (host in {'www.ti.com', 'www.vishay.com'}
                          and slug in parts and named_sheet(pdf.pages[0])) else ''
        applicable_parts = set()
        if urlsplit(url).hostname == 'www.infineon.com':
            cover = pdf.pages[0].extract_text(x_tolerance=1) or ''
            # The Type column, rather than arbitrary references in the narrative, identifies covered devices.
            _, header, part_table = cover.partition('Type Package Configuration')
            if header:
                applicable_parts = set(re.findall(r'(?m)^([A-Z0-9-]+)\*? +(?:SOT|SOD|TSLP|SC)\d?[-\w]* +', part_table))
        figure_terms = set(terms) & {'trr', 'recovery', 'measurement', 'measure', 'test', 'waveform', 'figure'}
        figure = None
        infineon_vr_fallback = []
        for page in pages:
            page_part = single if single and named_sheet(page) else document_part
            before_page = len(found)
            page_rows = []
            for table in page.find_tables():
                page_rows.extend(_read_table(page, table, parts, page_part, terms))
            if not page_rows and document_part:
                page_rows.extend(_text_rows(page, [document_part], terms))
            if (grade == 2 and host == 'www.vishay.com'
                    and 'vrrm' in {str(term).lower() for term in terms}):
                # Vishay BAS16 lists both VRM (non-repetitive) and
                # ``VRRM = VRWM = VR``. A VRRM request must never be satisfied
                # by the former row, even when both rows share the same table.
                page_rows = [item for item in page_rows
                             if _is_vishay_vrrm_symbol(item[1].get('symbol', ''))]
            if (grade == 2 and urlsplit(url).hostname == 'services.taiwansemi.com'
                    and set(terms) & {'vrrm', 'repetitive'}):
                vrrm = [item for item in page_rows if re.sub(r'\s+', '', item[1].get('symbol', '')).upper() == 'VRRM']
                if vrrm:
                    page_rows = vrrm
            found.extend(page_rows)
            if grade == 2 and len(found) == before_page and urlsplit(url).hostname == 'www.infineon.com':
                infineon_vr_fallback.extend(_infineon_reverse_voltage(page, parts, terms, applicable_parts))
            if figure_terms and figure is None:
                page_text = page.extract_text(x_tolerance=1) or ''
                if caption := FIGURE_CAPTION.search(page_text):
                    figure = _figure_png(page, caption.group(0))
            page.close()
        if infineon_vr_fallback and not any(
                re.sub(r'\s+', '', row.get('symbol', '')).upper() == 'VRRM'
                for _, row in found):
            found.extend((1, row) for row in infineon_vr_fallback)
        if figure:
            for _, row in found:
                if re.search(r'reverse recovery|recovery time', row.get('row', ''), re.I) or \
                        re.sub(r'[^a-z0-9]', '', row.get('symbol', '').lower()) == 'trr':
                    row['figure'] = figure
    return [row for _, row in sorted(found, key=lambda pair: -pair[0])[:MAX_ROWS]]


def verified_rows(raw, url, parts, terms, *, grade=None):
    """Network bytes are never written to disk. Limit time and (Linux) CPU/address space."""
    worker = Path(__file__).resolve()
    try:
        result = subprocess.run([sys.executable, '-I', str(worker), url, json.dumps(parts), json.dumps(terms), str(grade or '')],
                                input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=12, check=True,
                                env={k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'PATH', 'TMP', 'TEMP', 'LANG')
                                     if k in os.environ})
        rows = json.loads(result.stdout)
        if grade in (2, 3):
            digest = hashlib.sha256(raw).hexdigest()
            for row in rows:
                row['evidence_grade'] = grade
                row['source_url'] = official_pdf(url, grade=grade)
                row['source_sha256'] = digest
        return rows
    except (subprocess.SubprocessError, OSError, ValueError) as error:
        # [왜] 검증 하위 프로세스가 죽거나 시간이 넘어도 [](근거 없음)로만 보였다. 예외 종류와 stderr 마지막 한 줄만 남긴다(주소 · 질의 · 키는 적지 않는다)
        lines = (getattr(error, 'stderr', None) or b'').decode('utf-8', 'replace').strip().splitlines()
        LOGGER.warning('datasheet_verify_failed error=%s stderr_last=%s', type(error).__name__, lines[-1][:200] if lines else '')
        return []


if __name__ == '__main__':
    if sys.platform == 'linux':  # [왜] RLIMIT_AS는 Linux에서만 쓴다. macOS는 ValueError로 이 하위 프로세스가 죽는다(os.name == 'posix'는 macOS도 참)
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    grade = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
    print(json.dumps(extract(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1],
                             json.loads(sys.argv[2]), json.loads(sys.argv[3]), grade=grade)))
