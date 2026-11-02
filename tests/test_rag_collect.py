"""수집 도구(backend/rag/collect.py)를 네트워크 없이 지킨다: xlsx 목록 합치기, manifest로 받기, 실패 기록."""
import csv
import hashlib
import io
import json
import zipfile

from backend.rag import collect

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
PDF = b'%PDF-1.4 test'


def make_xlsx(path, rows):
    """첫 행이 제목인 아주 작은 xlsx(공유 글자 표 사용)를 만든다."""
    words = sorted({v for r in rows for v in r})
    sheet = ''.join(
        f'<row r="{i + 1}">' + ''.join(
            f'<c r="{chr(65 + k)}{i + 1}" t="s"><v>{words.index(v)}</v></c>' for k, v in enumerate(r) if v) + '</row>'
        for i, r in enumerate(rows))
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('xl/sharedStrings.xml', f'<sst xmlns="{NS}">' + ''.join(f'<si><t>{w}</t></si>' for w in words) + '</sst>')
        z.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="{NS}"><sheetData>{sheet}</sheetData></worksheet>')


def test_build_list_groups_parts_by_datasheet(tmp_path):
    url = 'https://example.com/ds/1N5817%20SERIES_H2104.pdf'
    make_xlsx(tmp_path / 'schottky.xlsx', [['Part Number', 'Datasheet'], ['1N5817', url], ['1N5819', url], ['X1', '']])
    out = tmp_path / 'list.csv'
    assert collect.build_list(tmp_path, out) == (1, 1)  # PDF 1개, 링크 없는 품번 1개
    (row,) = csv.DictReader(open(out, encoding='utf-8'))
    assert row['file'] == '1N5817 SERIES_H2104.pdf' and row['parts'] == '1N5817;1N5819' and row['categories'] == 'schottky'


def test_encode_escapes_spaces():
    assert collect.encode('https://a.b/x y.pdf') == 'https://a.b/x%20y.pdf'


def test_download_from_manifest_checks_pdf_and_sha(tmp_path, monkeypatch):
    good, bad_sha, html = 'good.pdf', 'bad.pdf', 'html.pdf'
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(''.join(json.dumps({'path': f'corpus/tsc/pdf/{f}', 'source_url': f'https://a.b/{f}', 'sha256': s}) + '\n'
                                for f, s in [(good, hashlib.sha256(PDF).hexdigest()), (bad_sha, '0' * 64), (html, None)]),
                        encoding='utf-8')
    monkeypatch.setattr(collect, 'PAUSE', 0)
    monkeypatch.setattr(collect.urllib.request, 'urlopen',
                        lambda url, timeout: io.BytesIO(b'<html>' if url.endswith(html) else PDF))
    pdf_dir = tmp_path / 'pdf'
    assert collect.download(str(manifest), str(pdf_dir)) == (1, 0, 2)
    assert (pdf_dir / good).read_bytes() == PDF and not (pdf_dir / bad_sha).exists()
    failed = {r['file']: r['error'] for r in csv.DictReader(open(tmp_path / 'failed.csv', encoding='utf-8'))}
    assert 'sha256' in failed[bad_sha] and 'PDF가 아님' in failed[html]
    assert collect.download(str(manifest), str(pdf_dir)) == (0, 1, 2)  # 다시 돌리면 받은 것은 건너뛴다
