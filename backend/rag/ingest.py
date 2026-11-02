"""카드와 임베딩을 DB 코퍼스 표(db/02_rag_corpus.sql)에 넣는다(오프라인 도구).

- 하는 일
  - manifest.jsonl의 문서를 source_documents에, chunks.jsonl의 카드를 document_chunks에 넣는다.
  - 카드마다 임베딩을 chunk_embeddings에 넣는다. 벡터는 본문 해시로 캐시(<벡터 폴더>/vectors.f32·vectors.sha.txt)에서
    다시 쓰고, 캐시에 없는 본문만 embed_texts로 만들어 캐시에 덧붙인다.
  - 다시 돌리면 이미 들어간 문서·카드·임베딩은 건너뛴다(지우지 않는다). DB에 임베딩이 있는 카드는 캐시가 없어도 API를 다시 부르지 않는다.
  - 캐시 파일이 쓰는 도중 끊겨 벡터와 sha 수가 어긋나면, 짝이 맞는 앞부분까지 잘라 복구한다.
- 하지 않는 일: 표 만들기(db/02_rag_corpus.sql), 검색(retrieve.py), 파싱·청킹(parse.py, chunk.py)
- 출처: docs/specs/rag-pipeline.md What 5·AC-04·EC-04·EC-05
- 필요한 것: DATABASE_URL, 캐시에 없는 본문이 있으면 임베딩 키(.env)

실행: python -m backend.rag.ingest <manifest.jsonl> <chunks.jsonl> <벡터 폴더> [--cache-only]
"""
import json
import os
import sys
import time

import numpy as np

from backend.rag.chunk import CHUNKER_VERSION, DOC_DEFAULTS, doc_key
from backend.rag.storage import vector_type

DIM = 1536
EMBED_MODEL = 'openai/text-embedding-3-small'
CORPUS_VERSION = 'tsc-diode-2026-11-01'
BATCH = 128
LABEL_MAX = 500  # document_chunks.table_name·row_label이 VARCHAR(500)이다
MAX_RETRY = 3  # [왜] 키 한도가 있어 실패한 묶음을 끝없이 다시 부르지 않는다(AGENTS 6)


class VectorCache:
    """본문 sha256 → 벡터. float32를 이어 붙인 파일과 같은 순서의 sha 목록 파일 한 쌍."""

    def __init__(self, folder):
        os.makedirs(folder, exist_ok=True)
        self.vec_path, self.sha_path = os.path.join(folder, 'vectors.f32'), os.path.join(folder, 'vectors.sha.txt')
        shas = open(self.sha_path, encoding='utf-8').read().split() if os.path.exists(self.sha_path) else []
        vecs = np.fromfile(self.vec_path, dtype=np.float32) if os.path.exists(self.vec_path) else np.zeros(0, np.float32)
        n = min(len(shas), len(vecs) // DIM)
        if n != len(shas) or len(vecs) != n * DIM:
            # [왜] 벡터와 sha를 쓰는 사이에 끊기면 두 파일의 개수가 어긋난다. 짝이 맞는 앞부분까지 잘라 다시 쓴다
            # (잘린 본문은 다음 실행에서 다시 임베딩된다)
            shas, vecs = shas[:n], vecs[:n * DIM]
            vecs.tofile(self.vec_path)
            with open(self.sha_path, 'w', encoding='utf-8') as fs:
                fs.write(''.join(s + '\n' for s in shas))
        self.vecs = vecs.reshape(n, DIM)
        self.index = {s: i for i, s in enumerate(shas)}

    def get(self, sha):
        return self.vecs[self.index[sha]]

    def add(self, pairs):
        """(sha, 벡터) 묶음을 파일 끝에 붙인다. 끊겨도 붙인 것까지는 남는다."""
        arr = np.asarray([v for _, v in pairs], dtype=np.float32)
        with open(self.vec_path, 'ab') as fv, open(self.sha_path, 'a', encoding='utf-8') as fs:
            arr.tofile(fv)
            fs.write(''.join(s + '\n' for s, _ in pairs))
        start = len(self.vecs)
        self.vecs = np.vstack([self.vecs, arr])
        self.index.update({s: start + i for i, (s, _) in enumerate(pairs)})


def fill_cache(cache, texts_by_sha):
    """캐시에 없는 본문을 BATCH개씩 임베딩해 캐시에 붙인다."""
    from backend.services.llm import embed_texts
    todo = [s for s in texts_by_sha if s not in cache.index]
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        for attempt in range(1, MAX_RETRY + 1):
            try:
                vectors, _, _, _ = embed_texts([texts_by_sha[s] for s in part])
                break
            except Exception:
                if attempt == MAX_RETRY:
                    raise
                time.sleep(2 * attempt)
        cache.add(list(zip(part, vectors)))
    return len(todo)


def main(manifest_path, chunks_path, vec_dir, cache_only=False):
    import psycopg
    from pgvector.psycopg import register_vector
    from pgvector import HalfVector
    kind = vector_type()
    # manifest에 없는 공통 값은 최신 main의 기본값으로 채우고 문서별 값이 앞선다.
    docs = [{**DOC_DEFAULTS, **json.loads(line)} for line in open(manifest_path, encoding='utf-8')]
    cards = [json.loads(line) for line in open(chunks_path, encoding='utf-8')]
    cache = VectorCache(vec_dir)
    texts = {c['sha256']: c['text'] for c in cards}
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        register_vector(conn)
        cur = conn.cursor()
        actual = cur.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                             "WHERE attrelid='chunk_embeddings'::regclass AND attname='embedding'").fetchone()[0]
        if actual != f'{kind}({DIM})':
            raise ValueError('RAG_VECTOR_TYPE and database embedding type do not match')
        for d in docs:  # 문서: 이미 있으면 건너뛴다
            cur.execute(
                'INSERT INTO source_documents (document_key, document_type, title, publisher, source_url, revision, license_text,'
                ' file_sha256, corpus_version, collected_at, parser, chars_original, chars_kept, truncated)'
                ' VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (document_key) DO NOTHING',
                (d['doc_id'], 'DATASHEET', d['title'], d['manufacturer'], d['source_url'], d['revision'], d['usage_conditions'],
                 d['sha256'], CORPUS_VERSION, d['collected_at'], d['parser'], d['chars_original'], d['chars_kept'], d['truncated']))
        cur.execute('SELECT document_key, id FROM source_documents')
        doc_id = dict(cur.fetchall())
        cur.execute('SELECT DISTINCT document_id FROM document_chunks')
        done = {r[0] for r in cur.fetchall()}
        # 카드: 카드가 하나도 없는 문서만 넣는다(문서 단위로 다 넣거나 안 넣거나)
        with cur.copy('COPY document_chunks (document_id, chunk_index, content, chunk_sha256, page_number,'
                      ' table_name, row_label, chunker_version) FROM STDIN') as cp:
            for c in cards:
                if doc_id[doc_key(c['doc'])] not in done:
                    # [주의] 면책 문구 같은 긴 첫 칸이 행 이름이 되는 표가 있다. 이름표 열만 자르고 본문(content)은 그대로 둔다
                    cp.write_row((doc_id[doc_key(c['doc'])], c['idx'], c['text'], c['sha256'], c['page'],
                                  c['table'] and c['table'][:LABEL_MAX], c['row'] and c['row'][:LABEL_MAX], CHUNKER_VERSION))
        # 임베딩: 이 모델의 임베딩이 없는 카드만 넣는다
        cur.execute('SELECT dc.id, dc.chunk_sha256 FROM document_chunks dc WHERE NOT EXISTS (SELECT 1 FROM chunk_embeddings ce'
                    ' WHERE ce.chunk_id = dc.id AND ce.embedding_model = %s)', (EMBED_MODEL,))
        rows = [(cid, s.strip()) for cid, s in cur.fetchall()]
        # [왜] 임베딩이 없는 카드의 본문만 캐시에 채운다. 캐시를 잃어도 DB에 이미 있는 임베딩은 다시 부르지 않는다
        unknown = {s for _, s in rows if s not in texts}
        if unknown:
            raise SystemExit(f'카드 파일에 없는 본문 해시 {len(unknown)}개: DB와 같은 chunks.jsonl을 주세요')
        if cache_only and any(s not in cache.index for _, s in rows):
            raise ValueError('cache-only: required vectors are missing; embedding API was not called')
        made = fill_cache(cache, {s: texts[s] for _, s in rows})
        with cur.copy('COPY chunk_embeddings (chunk_id, embedding_model, embedding) FROM STDIN WITH (FORMAT BINARY)') as cp:
            cp.set_types(['int8', 'varchar', kind])  # DB 열과 이진 COPY의 저장 형식을 함께 맞춘다
            for chunk_id, s in rows:
                vector = cache.get(s)
                cp.write_row((chunk_id, EMBED_MODEL, HalfVector(vector) if kind == 'halfvec' else vector))
        if rows:
            # [왜] 빈 표에 만든 HNSW 인덱스에 5만 행을 한꺼번에 넣으면 그래프가 나빠져 가까운 카드를 놓친다(11-01 실측:
            # 정확 검색 거리 0.345 카드를 놓치고 0.436 카드를 1위로 냄). 다 넣은 뒤 인덱스를 다시 만든다
            cur.execute("SET LOCAL maintenance_work_mem = '512MB'")
            cur.execute('REINDEX INDEX ix_chunk_embeddings_hnsw')
        for t in ('source_documents', 'document_chunks', 'chunk_embeddings'):
            cur.execute(f'SELECT count(*) FROM {t}')
            print(t, cur.fetchone()[0])
    print(f'새로 임베딩한 본문 {made}개, 이번에 넣은 임베딩 {len(rows)}개')


if __name__ == '__main__':
    cache_only = len(sys.argv) == 5 and sys.argv[4] == '--cache-only'
    if len(sys.argv) != 4 and not cache_only:
        sys.exit(__doc__)
    main(*sys.argv[1:4], cache_only=cache_only)
