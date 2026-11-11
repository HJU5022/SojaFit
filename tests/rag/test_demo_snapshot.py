"""데모 코퍼스 스냅샷(data/demo/snapshot/)이 기록과 같고, ingest.py가 읽는 모양이며, 같은 규칙으로 다시 뽑히는지 본다.

- 역할: 저장소의 스냅샷 두 파일의 sha256·문서 수·청크 수가 SNAPSHOT.md에 적힌 값과 같고 manifest 문서마다 청크가
  0번부터 빠짐없이 있는지 본다. 고르기 규칙은 가짜 원본으로 본다. DEMO_SNAPSHOT_SOURCE(저장소 밖 chunks-v4h 폴더)가
  있으면 그 원본에서 다시 뽑은 바이트가 같은지, 원본 summary.json의 청커 버전이 CHUNKER_VERSION과 같은지도 본다.
- 하지 않는 일: DB 적재(compose corpus-load), 검색 품질.
- 출처: data/demo/snapshot/SNAPSHOT.md, backend/rag/pipeline/demo_snapshot.py
"""
import hashlib
import json
import os
from pathlib import Path

import pytest

from backend.rag.pipeline import demo_snapshot
from backend.rag.pipeline.chunk import CHUNKER_VERSION, doc_key

SNAP = Path(__file__).resolve().parents[2] / 'data' / 'demo' / 'snapshot'
SOURCE = os.getenv('DEMO_SNAPSHOT_SOURCE')


def _jsonl(path):
    """jsonl 파일의 줄마다 사전."""
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def test_snapshot_matches_record_and_ingest_shape():
    """두 파일의 sha256·문서 수·청크 수가 SNAPSHOT.md와 같고, manifest 문서마다 청크 0..n-1이 모두 있다."""
    record = (SNAP / 'SNAPSHOT.md').read_text(encoding='utf-8')
    for name in ('manifest.jsonl', 'chunks.jsonl'):
        assert hashlib.sha256((SNAP / name).read_bytes()).hexdigest() in record, name
    manifest, chunks = _jsonl(SNAP / 'manifest.jsonl'), _jsonl(SNAP / 'chunks.jsonl')
    assert f'문서 {len(manifest)}건' in record and f'청크 {len(chunks):,}개' in record
    found = {}
    for c in chunks:
        found.setdefault(doc_key(c['doc']), []).append(c['idx'])
    # [왜] ingest.py는 manifest에 없는 문서의 청크에서 KeyError로 멈추고, 청크는 문서 단위로 다 넣거나 안 넣는다
    assert {k: sorted(v) for k, v in found.items()} == {m['doc_id']: list(range(m['chunks'])) for m in manifest}
    assert any('1N4148' in c['parts'] for c in chunks)


def test_select_rules(tmp_path, monkeypatch):
    """규칙 1~4에 걸린 문서만 앞 번호를 이유로 고르고, 같은 분류 문서는 이름 순 상한까지만 넣는다."""
    docs = {  # 파일 이름: (분류, 품번)
        '1N4148 SERIES_K2301.pdf': ('switching-diode-36', ['1N4148', '1N4148W']),
        '1N4148W SERIES_K1804.pdf': ('switching-diode-36', ['1N4148W']),
        'BAS16_F2001.pdf': ('switching-diode-36', ['BAS16']),
        'BAV99_A1.pdf': ('switching-diode-36', ['BAV99']),
        '1N4001G SERIES_P2104.pdf': ('standard-rectifier-12', ['1N4001G', '1N4007G']),
        '1N4001 SERIES_A1.pdf': ('standard-rectifier-12', ['1N4001']),
    }
    chunks = [{'doc': d, 'category': cat, 'parts': parts, 'idx': i, 'text': f'{d} {i}'}
              for d, (cat, parts) in docs.items() for i in range(2)]
    (tmp_path / 'chunks.jsonl').write_text(''.join(json.dumps(c) + '\n' for c in chunks), encoding='utf-8')
    (tmp_path / 'manifest.jsonl').write_text(''.join(json.dumps({'doc_id': doc_key(d)}) + '\n' for d in docs),
                                             encoding='utf-8')
    monkeypatch.setattr(demo_snapshot, 'FAMILY_MAX', 3)  # 같은 분류 4건 중 이름 순 앞 3건만
    manifest, picked, reason = demo_snapshot.select(tmp_path)
    assert reason == {'1N4148 SERIES_K2301.pdf': 1, '1N4148W SERIES_K1804.pdf': 2,
                      '1N4001G SERIES_P2104.pdf': 3, 'BAS16_F2001.pdf': 4}
    assert len(manifest.splitlines()) == 4 and len(picked.splitlines()) == 8


@pytest.mark.skipif(not SOURCE, reason='DEMO_SNAPSHOT_SOURCE(저장소 밖 chunks-v4h 폴더)가 있을 때만 돈다')
def test_snapshot_regenerates_from_source():
    """원본에서 다시 뽑은 두 파일이 저장소 파일과 바이트까지 같고, 원본의 청커 버전이 적재 코드와 같다."""
    manifest, chunks, _ = demo_snapshot.select(SOURCE)
    assert manifest == (SNAP / 'manifest.jsonl').read_bytes()
    assert chunks == (SNAP / 'chunks.jsonl').read_bytes()
    summary = json.loads((Path(SOURCE) / 'summary.json').read_text(encoding='utf-8'))
    assert summary['chunker_version'] == CHUNKER_VERSION
