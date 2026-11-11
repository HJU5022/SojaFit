"""공식 PDF와 Docling의 외형 그림 페이지를 연결하는 오프라인/런타임 계약."""
import importlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest


URL = 'https://services.taiwansemi.com/storage/resources/datasheet/SS34.pdf'
ROOT = Path(__file__).resolve().parents[2]


def _module():
    assert importlib.util.find_spec('backend.rag.pipeline.package_outlines') is not None
    return importlib.import_module('backend.rag.pipeline.package_outlines')


def _fixture(tmp_path, *, urls=None, docs=None):
    folder = tmp_path / 'docling'
    folder.mkdir()
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(''.join(json.dumps({'source_url': url}) + '\n' for url in (urls or [URL])), encoding='utf-8')
    if docs is None:
        docs = [{'origin': {'filename': 'SS34.pdf'}, 'texts': [
            {'text': 'DIMENSIONS', 'prov': [{'page_no': 6}]},
            {'text': 'PACKAGE OUTLINE', 'prov': [{'page_no': 5}]},
        ], 'pictures': [{'prov': [{'page_no': 5}]}, {'prov': [{'page_no': 6}]}]}]
    for number, doc in enumerate(docs):
        (folder / f'{number}.json').write_text(json.dumps(doc), encoding='utf-8')
    return folder, manifest


def test_outline_index_picks_first_heading_page_with_picture(tmp_path):
    folder, manifest = _fixture(tmp_path)
    result = _module().build_outline_index(folder, manifest)
    assert result == {'ss34.pdf': {'source_url': URL, 'outline_page': 5, 'heading': 'PACKAGE OUTLINE'}}


def test_heading_without_same_page_picture_is_rejected(tmp_path):
    folder, manifest = _fixture(tmp_path, docs=[{'origin': {'filename': 'SS34.pdf'},
        'texts': [{'text': 'PACKAGE OUTLINE', 'prov': [{'page_no': 5}]}],
        'pictures': [{'prov': [{'page_no': 4}]}]}])
    with pytest.raises(ValueError, match='SS34.pdf'):
        _module().build_outline_index(folder, manifest)


def test_manifest_without_docling_is_rejected(tmp_path):
    folder, manifest = _fixture(tmp_path, docs=[])
    with pytest.raises(ValueError, match='SS34.pdf'):
        _module().build_outline_index(folder, manifest)


def test_docling_without_manifest_is_rejected(tmp_path):
    folder, manifest = _fixture(tmp_path, urls=[URL.replace('SS34', 'SS35')])
    with pytest.raises(ValueError):
        _module().build_outline_index(folder, manifest)


def test_duplicate_normalized_manifest_basenames_are_rejected(tmp_path):
    folder, manifest = _fixture(tmp_path, urls=[URL, URL.replace('SS34', 'ss34')])
    with pytest.raises(ValueError, match='duplicate'):
        _module().build_outline_index(folder, manifest)


def test_duplicate_docling_origin_is_rejected(tmp_path):
    doc = {'origin': {'filename': 'SS34.pdf'}, 'texts': [], 'pictures': []}
    folder, manifest = _fixture(tmp_path, docs=[doc, doc])
    with pytest.raises(ValueError, match='duplicate'):
        _module().build_outline_index(folder, manifest)


@pytest.mark.parametrize('url', ['http://example.org/SS34.pdf', 'C:/private/SS34.pdf',
    'https:///SS34.pdf', 'https://user:password@example.org/SS34.pdf',
    'https://example.org/SS34.pdf#page=999', 'https://example.org/SS34.pdf?redirect=bad',
    'javascript:alert(1)', 'https://example.org/SS34%0a.pdf', 'https://bad host/SS34.pdf'])
def test_invalid_source_urls_are_rejected(tmp_path, url):
    folder, manifest = _fixture(tmp_path, urls=[url])
    with pytest.raises(ValueError):
        _module().build_outline_index(folder, manifest)


def test_url_decoded_manifest_basename_matches_exact_origin(tmp_path):
    folder, manifest = _fixture(tmp_path, urls=[URL.replace('SS34', 'SS%2034')], docs=[{
        'origin': {'filename': 'SS 34.pdf'}, 'texts': [{'text': 'outline dimensions', 'prov': [{'page_no': 2}]}],
        'pictures': [{'prov': [{'page_no': 2}]}]}])
    assert _module().build_outline_index(folder, manifest)['ss 34.pdf']['outline_page'] == 2


def test_manifest_and_docling_join_uses_casefolded_exact_basename(tmp_path):
    folder, manifest = _fixture(tmp_path, urls=[URL.replace('SS34.pdf', 'Ss%2034.PDF')], docs=[{
        'origin': {'filename': 'sS 34.pdf'}, 'texts': [{'text': 'PACKAGE OUTLINE', 'prov': [{'page_no': 2}]}],
        'pictures': [{'prov': [{'page_no': 2}]}]}])
    assert _module().build_outline_index(folder, manifest) == {
        'ss 34.pdf': {'source_url': 'https://services.taiwansemi.com/storage/resources/datasheet/Ss%2034.PDF',
                      'outline_page': 2, 'heading': 'PACKAGE OUTLINE'}}


def test_checked_in_index_covers_manifest():
    _module()
    manifest = [json.loads(line) for line in (ROOT / 'data/manifest.jsonl').read_text(encoding='utf-8').splitlines() if line]
    index = json.loads((ROOT / 'data/package-outline-pages.json').read_text(encoding='utf-8'))
    assert len(manifest) == len(index) == 1360
    assert {unquote(urlsplit(row['source_url']).path.rsplit('/', 1)[-1]).casefold() for row in manifest} == set(index)
    assert list(index) == sorted(index)
    assert all(row['source_url'].startswith('https://') and row['outline_page'] >= 1 for row in index.values())
    assert all(set(row) == {'source_url', 'outline_page', 'heading'} for row in index.values())


def test_cli_is_deterministic_and_prints_counts(tmp_path):
    _module()
    folder, manifest = _fixture(tmp_path)
    output = tmp_path / 'index.json'
    command = [sys.executable, '-m', 'backend.rag.pipeline.package_outlines', str(folder), str(manifest), str(output)]
    first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    contents = output.read_bytes()
    second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    assert first.stdout.strip() == second.stdout.strip() == 'manifest=1 docling=1 indexed=1 exceptions=0'
    assert output.read_bytes() == contents
    assert str(tmp_path) not in contents.decode('utf-8')


@pytest.mark.parametrize('document', ['1N4148 SERIES_K2301.pdf', 'C:\\private\\1N4148 SERIES_K2301.pdf',
    '/private/1n4148%20series_k2301.PDF'])
def test_runtime_exact_lookup_uses_only_canonical_metadata(document):
    assert importlib.util.find_spec('backend.rag.source_metadata') is not None
    from backend.rag.source_metadata import source_metadata
    assert source_metadata(document) == {'source_url':
        'https://services.taiwansemi.com/storage/resources/datasheet/1N4148 SERIES_K2301.pdf', 'outline_page': 4}


@pytest.mark.parametrize('document', ['unknown.pdf', 'prefix1N4148 SERIES_K2301.pdf',
    'https://evil.example/1N4148 SERIES_K2301.pdf', 'javascript:1N4148 SERIES_K2301.pdf',
    'x://evil.example/1N4148%20SERIES_K2301.pdf',
    'ht\ttps://evil.example/1N4148%20SERIES_K2301.pdf',
    'private\t/1N4148 SERIES_K2301.pdf'])
def test_runtime_rejects_unknown_documents_and_caller_urls(document):
    assert importlib.util.find_spec('backend.rag.source_metadata') is not None
    from backend.rag.source_metadata import source_metadata
    assert source_metadata(document) is None
