import json

import pytest

from backend.mcp_skill.mcp_server import server


def test_manifest_tool_returns_exact_document_metadata(tmp_path, monkeypatch):
    manifest = tmp_path / 'manifest.jsonl'
    rows = [
        {'doc_id': 'tsc-a', 'title': 'A', 'revision': 'R1', 'source_url': 'https://services.taiwansemi.com/a.pdf', 'sha256': 'a' * 64, 'bytes': 100, 'pages': 4},
        {'doc_id': 'tsc-b', 'title': 'B', 'revision': 'R2', 'source_url': 'https://services.taiwansemi.com/b.pdf', 'sha256': 'b' * 64, 'bytes': 80, 'pages': 2},
    ]
    manifest.write_text(''.join(json.dumps(x) + '\n' for x in rows), encoding='utf-8')
    monkeypatch.setattr(server, 'MANIFEST_PATH', manifest)
    actual = server.get_corpus_document('tsc-b')
    assert actual == {'status': 'found', 'document': rows[1], 'pdf_verified': False}


def test_manifest_tool_distinguishes_missing_document_and_unavailable_manifest(tmp_path, monkeypatch):
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(json.dumps({'doc_id': 'tsc-a'}) + '\n', encoding='utf-8')
    monkeypatch.setattr(server, 'MANIFEST_PATH', manifest)
    assert server.get_corpus_document('tsc-absent') == {'status': 'not_found', 'document': None, 'pdf_verified': False}
    manifest.write_text('{broken json\n', encoding='utf-8')
    assert server.get_corpus_document('tsc-a') == {'status': 'unavailable', 'document': None, 'pdf_verified': False}
    manifest.unlink()
    assert server.get_corpus_document('tsc-a') == {'status': 'unavailable', 'document': None, 'pdf_verified': False}


@pytest.mark.parametrize('doc_id', ['', '  ', 'x' * 201])
def test_manifest_tool_rejects_invalid_document_id(doc_id):
    with pytest.raises(ValueError):
        server.get_corpus_document(doc_id)
