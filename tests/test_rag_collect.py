"""수집 도구(backend/rag/collect.py)를 네트워크 없이 지킨다.

- 역할: xlsx 목록 합치기, manifest로 받기(파일 이름은 source_url 끝, sha256 대조, PDF 아님·해시 다름은 failed.csv), 다시 돌리면 건너뛰기를 확인한다.
- 하지 않는 일: 실제 다운로드는 하지 않는다.
- 출처: docs/specs/rag-pipeline.md What 1·2, EC-01·EC-09
"""
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
    manifest.write_text(''.join(json.dumps({'source_url': f'https://a.b/{f}', 'sha256': s}) + '\n'
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


def test_encode_does_not_double_escape():
    assert collect.encode('https://a.b/x%20y.pdf') == 'https://a.b/x%20y.pdf'


def test_read_targets_rejects_non_https_and_path_traversal(tmp_path):
    bad = tmp_path / 'bad.csv'
    bad.write_text('file,url\nx.pdf,file:///etc/passwd\n', encoding='utf-8')
    try:
        collect.read_targets(str(bad))
    except ValueError:
        pass
    else:
        raise AssertionError('file:// 주소를 받아들였다')
    trav = tmp_path / 'trav.csv'
    trav.write_text('file,url\n../../x.pdf,https://a.b/x.pdf\n', encoding='utf-8')
    assert collect.read_targets(str(trav))[0]['file'] == 'x.pdf'  # 폴더 밖으로 나가지 못한다


def test_manifest_file_name_is_unquoted(tmp_path):
    m = tmp_path / 'm.jsonl'
    m.write_text(json.dumps({'source_url': 'https://a.b/1N4148%20SERIES_K2301.pdf'}) + '\n', encoding='utf-8')
    assert collect.read_targets(str(m))[0]['file'] == '1N4148 SERIES_K2301.pdf'
