"""고정 카드·벡터·질문 캐시로 halfvec 실험을 재현한다. API는 호출하지 않는다."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import psycopg
from dotenv import dotenv_values
from pgvector.psycopg import register_vector
from psycopg.conninfo import conninfo_to_dict, make_conninfo

REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / 'evals/results/halfvec_inputs_2026-11-02.json'
VERSION = 'local-rebuild-1360-no-unverified-cover-2026-11-02'
MODEL = 'openai/text-embedding-3-small'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_cache(folder):
    keys = (folder / 'vectors.sha.txt').read_text().split()
    values = np.fromfile(folder / 'vectors.f32', dtype=np.float32)
    if len(set(keys)) != len(keys) or values.size != len(keys) * 1536 or not np.isfinite(values).all():
        raise ValueError('invalid cache; files were not modified')
    return dict(zip(keys, values.reshape(-1, 1536)))


def validate_inputs(inputs, record=None):
    record = record if record is not None else json.loads(RECORD.read_text())
    for name, expected in record['files'].items():
        path = inputs / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f'input hash mismatch: {name}')
    return record


def questions(dataset, cache):
    from evals.run_retrieval import gold_locations
    items = [json.loads(line) for line in dataset.read_text().splitlines()]
    texts = [r['input'] for r in items if r['kind'] == 'relevant' and gold_locations(r['gold_chunks'])]
    if any(hashlib.sha256(q.encode()).hexdigest() not in cache for q in texts):
        raise ValueError('missing question cache; API disabled')
    return texts


def cached_embed(cache):
    def embed(texts):
        return [cache[hashlib.sha256(t.encode()).hexdigest()].tolist() for t in texts], 0, 'openrouter', MODEL
    return embed


def local_dsn(env_file):
    dsn = dotenv_values(env_file).get('DATABASE_URL', '')
    if conninfo_to_dict(dsn).get('host') not in {'127.0.0.1', 'localhost', '::1'}:
        raise ValueError('localhost database required')
    return dsn


def db_snapshot(dsn, kind, record, expected_cards):
    from backend.rag import storage
    with psycopg.connect(dsn) as conn:
        register_vector(conn)
        conn.execute('SET TRANSACTION READ ONLY')
        snap = storage.snapshot(conn)
        if snap['embedding_type'] != f'{kind}(1536)':
            raise ValueError('database embedding type mismatch')
        if conn.execute("SELECT to_regclass('ix_chunk_embeddings_hnsw')").fetchone()[0] is not None:
            raise ValueError('HNSW must be absent in both databases')
        counts = {t: conn.execute('SELECT count(*) FROM ' + t).fetchone()[0]
                  for t in ['source_documents', 'document_chunks', 'chunk_embeddings']}
        if conn.execute('SELECT count(*) FROM chunk_embeddings WHERE embedding_model<>%s', (MODEL,)).fetchone()[0]:
            raise ValueError('database embedding model mismatch')
        if counts != record['counts']:
            raise ValueError('database row count mismatch')
        rows = conn.execute('SELECT dc.id, d.document_key, dc.chunk_index, dc.chunk_sha256 '
                            'FROM document_chunks dc JOIN source_documents d ON d.id=dc.document_id ORDER BY dc.id').fetchall()
        if rows != expected_cards:
            raise ValueError('database card order/hash mismatch')
        return {'counts': counts, 'storage': snap}


def load(inputs, env_file, record):
    from backend.rag import ingest
    from backend.services import llm
    cache = read_cache(inputs / 'cache')
    cards = [json.loads(line) for line in (inputs / 'chunks.jsonl').read_text().splitlines()]
    if any(c['sha256'] not in cache for c in cards):
        raise ValueError('missing document cache; API disabled')
    llm.embed_texts = cached_embed(cache)
    dsn = local_dsn(env_file)
    with psycopg.connect(dsn) as conn:
        if conn.execute('SELECT count(*) FROM source_documents WHERE corpus_version<>%s', (VERSION,)).fetchone()[0]:
            raise ValueError('database contains another corpus')
    os.environ['DATABASE_URL'], os.environ['RAG_VECTOR_TYPE'] = dsn, 'vector'
    ingest.CORPUS_VERSION = ingest.CHUNKER_VERSION = VERSION
    ingest.main(str(inputs / 'manifest.jsonl'), str(inputs / 'chunks.jsonl'), str(inputs / 'cache'), cache_only=True)
    validate_inputs(inputs, record)


def compare(args, record):
    from backend.rag import storage
    from backend.rag.chunk import doc_key
    from backend.services import llm
    from evals import run_retrieval
    dataset = REPO / 'evals/dataset_v1.jsonl'
    frozen = json.loads((REPO / 'evals/FROZEN.json').read_text())
    if digest(dataset) != frozen['dataset_v1.jsonl']['sha256'] or digest(dataset) != record['dataset_sha256']:
        raise ValueError('frozen dataset hash mismatch')
    cache = read_cache(args.inputs / 'query-cache')
    questions(dataset, cache)  # Fail before any search if a query is absent.
    llm.embed_texts, llm.DEMO_MODE = cached_embed(cache), False
    cards = [json.loads(line) for line in (args.inputs / 'chunks.jsonl').read_text().splitlines()]
    expected = [(i, doc_key(c['doc']), c['idx'], c['sha256']) for i, c in enumerate(cards, 1)]
    dsns = {'vector': local_dsn(args.vector_env), 'halfvec': local_dsn(args.halfvec_env)}
    snapshots = {k: db_snapshot(d, k, record, expected) for k, d in dsns.items()}
    args.out.mkdir(exist_ok=False)
    with psycopg.connect(dsns['vector']) as conn:
        register_vector(conn)
        conn.execute('SET TRANSACTION READ ONLY')
        result = storage.compare(conn, samples=1000, max_seconds=args.max_seconds)
    (args.out / 'precision.json').write_text(json.dumps(result, indent=1) + '\n')
    summaries = {}
    for kind, dsn in dsns.items():
        os.environ['DATABASE_URL'] = make_conninfo(dsn, options='-cdefault_transaction_read_only=on')
        os.environ['RAG_VECTOR_TYPE'] = kind
        path = args.out / f'retrieval-{kind}.json'
        run_retrieval.main(str(dataset), str(path), 5)
        data = json.loads(path.read_text())
        data['summary']['dataset'] = 'evals/dataset_v1.jsonl'
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')
        summaries[kind] = data['summary']
    if digest(dataset) != record['dataset_sha256']:
        raise ValueError('dataset changed during comparison')
    validate_inputs(args.inputs, record)
    report = {'api_calls': 0, 'storage': snapshots, 'retrieval': summaries,
              'card_comparison_complete': result['complete'], 'adoption_approved': False}
    (args.out / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n')
    if not result['complete']:
        raise SystemExit('incomplete card comparison; results preserved')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['verify', 'load', 'compare']:
        p = sub.add_parser(name)
        p.add_argument('--inputs', type=Path, required=True)
        if name == 'load':
            p.add_argument('--db-env', type=Path, required=True)
        if name == 'compare':
            p.add_argument('--vector-env', type=Path, required=True)
            p.add_argument('--halfvec-env', type=Path, required=True)
            p.add_argument('--out', type=Path, required=True)
            p.add_argument('--max-seconds', type=int, default=600)
    args = parser.parse_args()
    if args.command == 'compare' and not 1 <= args.max_seconds <= 600:
        parser.error('--max-seconds must be 1..600')
    record = validate_inputs(args.inputs)
    dataset = REPO / 'evals/dataset_v1.jsonl'
    frozen = json.loads((REPO / 'evals/FROZEN.json').read_text())
    if digest(dataset) != record['dataset_sha256'] or digest(dataset) != frozen['dataset_v1.jsonl']['sha256']:
        raise ValueError('frozen dataset hash mismatch')
    if args.command == 'load':
        load(args.inputs, args.db_env, record)
    elif args.command == 'compare':
        compare(args, record)
    else:
        read_cache(args.inputs / 'cache')
        questions(REPO / 'evals/dataset_v1.jsonl', read_cache(args.inputs / 'query-cache'))
        print('input hashes and caches verified; API calls: 0')


if __name__ == '__main__':
    main()
