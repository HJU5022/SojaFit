"""TSC 다이오드 데이터시트 목록을 만들고 PDF를 받는다(서버가 import하지 않는 오프라인 도구).

- 역할: 오프라인 CLI(`python -m backend.rag.collect`). 서버가 import하지 않는다.
  - list: TSC 분류 페이지의 Export xlsx 13개를 PDF 하나당 한 줄인 csv로 합친다(품번 여러 개가 계열 PDF 하나를 같이 쓴다).
  - download: 목록 csv 또는 저장소의 data/manifest.jsonl에 적힌 PDF를 원래 파일 이름으로 받는다. 이미 받은 파일은 건너뛰고,
    manifest로 받을 때는 sha256이 manifest와 같은지 본다. 실패는 pdf 폴더 옆 failed.csv에 남긴다.
    [왜] xlsx 목록은 저장소 밖에 있어서, 새 clone에서는 manifest만으로 같은 코퍼스를 받는다.
- 하지 않는 일: PDF를 읽거나 고치지 않는다(TSC 약관의 "비수정" 조건). 사이트 목록 페이지에 직접 접속하지 않는다.
- 출처: docs/specs/rag-pipeline.md What 1·2·EC-01·EC-09, TSC 이용 약관(https://www.taiwansemi.com/en/legal/) 3절 b항

실행:
  python -m backend.rag.collect list <xlsx 폴더> <목록 csv>
  python -m backend.rag.collect download <목록 csv 또는 data/manifest.jsonl> <pdf 폴더> [받을 개수]
"""
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from urllib.parse import quote, unquote, urlparse, urlsplit, urlunsplit

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'  # xlsx 안 XML의 이름공간
PAUSE = 1.5  # [왜] TSC 서버에 요청을 몰아 보내지 않으려고 파일 하나마다 쉰다
FIELDS = ['file', 'url', 'categories', 'n_parts', 'parts']


def read_xlsx(path):
    """xlsx 첫 시트를 {열 제목: 값} 사전의 목록으로 읽는다."""
    # [왜] xlsx는 XML 여러 개를 묶은 zip이라 표준 라이브러리만으로 읽는다
    with zipfile.ZipFile(path) as z:
        return _read_sheet(z)


def _read_sheet(z):
    """열린 xlsx(zip)의 첫 시트를 read_xlsx와 같은 모양으로 읽는다."""
    shared = []  # 글자 칸은 값 대신 sharedStrings.xml의 번호를 들고 있다
    if 'xl/sharedStrings.xml' in z.namelist():
        shared = [''.join(t.text or '' for t in si.iter(NS + 't'))
                  for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(NS + 'si')]
    rows = []
    for r in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).iter(NS + 'row'):
        row = {}
        for c in r.findall(NS + 'c'):
            col = re.match(r'[A-Z]+', c.get('r')).group()  # 칸 주소 "B12"에서 열 "B"
            v = c.find(NS + 'v')
            if v is None:  # [주의] 글자를 칸 안에 바로 넣는 경우(inlineStr)
                row[col] = ''.join(t.text or '' for t in c.iter(NS + 't'))
            else:
                row[col] = shared[int(v.text)] if c.get('t') == 's' else v.text
        rows.append(row)
    header = {name: col for col, name in rows[0].items()}  # 분류마다 열 구성이 달라 제목으로 찾는다
    return [{name: r.get(col, '') or '' for name, col in header.items()} for r in rows[1:]]


def build_list(xlsx_dir, out_csv):
    """제품 목록들을 데이터시트 링크 기준으로 묶어 csv로 쓰고 (PDF 수, 링크 없는 품번 수)를 돌려준다."""
    parts, cats, no_sheet = defaultdict(set), defaultdict(set), 0
    for f in sorted(os.listdir(xlsx_dir)):
        if not f.endswith('.xlsx'):
            continue
        for r in read_xlsx(os.path.join(xlsx_dir, f)):
            url = r['Datasheet'].strip()
            if not url:
                no_sheet += 1
                continue
            parts[url].add(r['Part Number'].strip())
            cats[url].add(f[:-5])  # 파일 이름이 분류 이름
    lines = [{'file': unquote(os.path.basename(urlparse(u).path)), 'url': u, 'categories': ';'.join(sorted(cats[u])),
              'n_parts': len(parts[u]), 'parts': ';'.join(sorted(parts[u]))} for u in sorted(parts)]
    names = [x['file'] for x in lines]
    assert all(u.startswith('https://') for u in parts)  # [주의] https만 받는다(download도 같은 검사를 한다)
    assert len(names) == len(set(names)), '파일 이름이 겹치면 받을 때 서로 덮어쓴다'
    with open(out_csv, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(lines)
    return len(lines), no_sheet


def encode(url):
    """주소 경로의 공백 같은 글자를 %20 형태로 바꿔 urlopen에 줄 수 있게 한다. 이미 %20인 주소도 두 번 바꾸지 않는다."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, quote(unquote(p.path)), p.query, p.fragment))


def read_targets(list_path):
    """목록 csv 또는 manifest.jsonl에서 {file, url, sha256} 목록을 읽는다. csv에는 sha256이 없다."""
    if list_path.endswith('.jsonl'):
        with open(list_path, encoding='utf-8') as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        # [왜] manifest는 크기를 줄이려고 path를 빼고 원래 파일 이름을 source_url 끝에서 얻는다. path가 있는 줄은 path를 쓴다
        out = [{'file': os.path.basename(r.get('path') or unquote(urlparse(r['source_url']).path)), 'url': r['source_url'],
                'sha256': r.get('sha256')} for r in rows]
    else:
        with open(list_path, encoding='utf-8') as fh:
            out = [{'file': os.path.basename(r['file']), 'url': r['url'], 'sha256': None} for r in csv.DictReader(fh)]
    for t in out:  # [주의] file:// 같은 다른 방식 주소나 ../가 든 이름이면 로컬 파일을 읽거나 pdf 폴더 밖에 쓸 수 있다
        if not t['url'].startswith('https://') or not t['file']:
            raise ValueError(f'https 주소와 파일 이름이 필요하다: {t}')
    return out


def download(list_path, pdf_dir, limit=None):
    """목록의 PDF를 차례로 받고 (새로 받음, 이미 있음, 실패) 수를 돌려준다."""
    rows = read_targets(list_path)[:limit]
    os.makedirs(pdf_dir, exist_ok=True)
    got, skipped, failed = 0, 0, []
    for r in rows:
        dest = os.path.join(pdf_dir, r['file'])
        if os.path.exists(dest):  # [왜] 끊겨도 다시 돌리면 이어서 받는다
            skipped += 1
            continue
        try:
            with urllib.request.urlopen(encode(r['url']), timeout=60) as resp:
                data = resp.read()
            if not data.startswith(b'%PDF'):  # [주의] 주소가 틀리면 오류 페이지(HTML)가 온다(EC-01)
                raise ValueError(f'PDF가 아님 ({len(data)} bytes)')
            if r['sha256'] and hashlib.sha256(data).hexdigest() != r['sha256']:  # 같은 이름의 새 개정판이면 코퍼스가 달라진다
                raise ValueError('sha256이 manifest와 다름')
            with open(dest + '.part', 'wb') as f:  # [왜] 다 쓴 뒤 이름을 바꿔 반쯤 받은 파일이 남지 않게 한다
                f.write(data)
            os.replace(dest + '.part', dest)
            got += 1
        except Exception as e:
            failed.append({'file': r['file'], 'url': r['url'], 'error': str(e)})
        time.sleep(PAUSE)
    # [왜] manifest는 저장소 안(data/)에 있으므로 실패 목록은 pdf 폴더 옆(저장소 밖)에 쓴다
    fail_path = os.path.join(os.path.dirname(os.path.abspath(pdf_dir)), 'failed.csv')
    if failed:
        with open(fail_path, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=['file', 'url', 'error'])
            w.writeheader()
            w.writerows(failed)
    elif os.path.exists(fail_path):
        os.remove(fail_path)
    return got, skipped, len(failed)


if __name__ == '__main__':
    cmd, *args = sys.argv[1:]
    if cmd == 'list':
        print('PDF %d개, 데이터시트 링크 없는 품번 %d개' % build_list(*args))
    elif cmd == 'download':
        print('새로 받음 %d, 이미 있음 %d, 실패 %d' % download(args[0], args[1], int(args[2]) if len(args) > 2 else None))
    else:
        sys.exit(__doc__)
