"""청크와 임베딩을 DB 코퍼스 표(db/002_rag_corpus.sql)에 넣는다(오프라인 도구).

- 역할: 오프라인 CLI(`python -m backend.rag.pipeline.ingest`). 서버가 import하지 않는다.
  - manifest.jsonl의 문서를 source_documents에, chunks.jsonl의 청크를 document_chunks에 넣는다.
    문서 분류(source_documents.category, db/012)는 청크의 category를 specs.py와 같은 family()로 바꿔 넣는다.
  - 청크마다 임베딩을 chunk_embeddings에 넣는다. 벡터는 본문 해시로 캐시(<벡터 폴더>/vectors.f32·vectors.sha.txt)에서
    다시 쓰고, 캐시에 없는 본문만 embed_texts로 만들어 캐시에 덧붙인다.
  - 다시 돌리면 이미 들어간 문서·청크·임베딩은 건너뛴다(지우지 않는다). DB에 임베딩이 있는 청크는 캐시가 없어도 API를 다시 부르지 않는다.
  - 캐시 파일이 쓰는 도중 끊겨 벡터와 sha 수가 어긋나면, 짝이 맞는 앞부분까지 잘라 복구한다.
- 하지 않는 일: 표 만들기(db/002_rag_corpus.sql), 검색(retrieve.py), 파싱·청킹(parse.py, chunk.py)
- 출처: docs/specs/rag-pipeline.md What 5·AC-04·AC-12·EC-04·EC-05
- 필요한 것: DATABASE_URL, 캐시에 없는 본문이 있으면 임베딩 키(.env)

- voyage-4-large 적재(`--voyage`): 미리 만든 청크 벡터(`<벡터 폴더>/v4large.f32`·`v4large.sha.txt`, 1024차원)를 이미 들어간 청크에 붙인다.
  임베딩 API를 부르지 않는다. 열이 차원 없는 halfvec이어야 한다(db/008). 모델 행이 있는 청크는 건너뛴다.

- voyage-4-large 캐시 채우기(`--voyage-fill`): chunks.jsonl 본문 중 `v4large` 캐시에 없는 것만 voyage_embed로 임베딩해 붙인다.
  DB에 쓰지 않는다. 청크를 다시 자른 뒤 `--voyage` 앞에 돌린다.

실행: python -m backend.rag.pipeline.ingest <manifest.jsonl> <chunks.jsonl> <벡터 폴더> [--cache-only | --chunks-only]
      python -m backend.rag.pipeline.ingest --voyage-fill <chunks.jsonl> <벡터 폴더>
      python -m backend.rag.pipeline.ingest --voyage <벡터 폴더>
"""
import json
import os
import sys
import time

import numpy as np

from backend.rag.pipeline.chunk import CHUNKER_VERSION, DOC_DEFAULTS, doc_key
from backend.rag.pipeline.specs import family
from backend.rag.storage import vector_type

DIM = 1536  # 임베딩 차원. 캐시 파일을 DIM개씩 끊어 읽으므로 모델을 바꾸면 캐시도 새로 만든다
EMBED_MODEL = 'openai/text-embedding-3-small'
CORPUS_VERSION = 'tsc-diode-2026-11-01'
VOYAGE_MODEL, VOYAGE_DIM = 'voyage-4-large', 1024  # 미리 만든 청크 벡터의 모델과 차원
BATCH = 128  # 임베딩 API를 한 번 부를 때 보내는 본문 수
LABEL_MAX = 500  # document_chunks.table_name·row_label이 VARCHAR(500)이다
MAX_RETRY = 3  # [왜] 키 한도가 있어 실패한 묶음을 끝없이 다시 부르지 않는다(AGENTS 6)


class VectorCache:
    """본문 sha256 → 벡터 캐시. float32를 이어 붙인 파일과 같은 순서의 sha 목록 파일 한 쌍이다."""

    def __init__(self, folder, stem='vectors', dim=DIM):
        """folder의 캐시 파일 한 쌍(<stem>.f32·<stem>.sha.txt, 벡터 차원 dim)을 읽고, 개수가 어긋나 있으면 짝이 맞는 앞부분만 남겨 고쳐 쓴다."""
        os.makedirs(folder, exist_ok=True)
        self.vec_path, self.sha_path = os.path.join(folder, f'{stem}.f32'), os.path.join(folder, f'{stem}.sha.txt')
        shas = open(self.sha_path, encoding='utf-8').read().split() if os.path.exists(self.sha_path) else []
        vecs = np.fromfile(self.vec_path, dtype=np.float32) if os.path.exists(self.vec_path) else np.zeros(0, np.float32)
        n = min(len(shas), len(vecs) // dim)
        if n != len(shas) or len(vecs) != n * dim:
            # [왜] 벡터와 sha를 쓰는 사이에 끊기면 두 파일의 개수가 어긋난다. 짝이 맞는 앞부분까지 잘라 다시 쓴다
            # (잘린 본문은 다음 실행에서 다시 임베딩된다)
            shas, vecs = shas[:n], vecs[:n * dim]
            vecs.tofile(self.vec_path)
            with open(self.sha_path, 'w', encoding='utf-8') as fs:
                fs.write(''.join(s + '\n' for s in shas))
        self.vecs = vecs.reshape(n, dim)  # 이어 붙인 1차원 float32를 (청크 수, dim) 표로 본다
        self.index = {s: i for i, s in enumerate(shas)}

    def get(self, sha):
        """본문 sha256의 벡터(float32). 캐시에 없으면 KeyError."""
        return self.vecs[self.index[sha]]

    def add(self, pairs):
        """(sha, 벡터) 묶음을 파일 끝에 붙인다."""
        # [왜] 'ab'·'a'로 끝에 덧붙이므로 도중에 끊겨도 붙인 것까지는 남는다. 어긋남은 __init__이 복구한다
        arr = np.asarray([v for _, v in pairs], dtype=np.float32)
        with open(self.vec_path, 'ab') as fv, open(self.sha_path, 'a', encoding='utf-8') as fs:
            arr.tofile(fv)
            fs.write(''.join(s + '\n' for s, _ in pairs))
        start = len(self.vecs)
        self.vecs = np.vstack([self.vecs, arr])
        self.index.update({s: start + i for i, (s, _) in enumerate(pairs)})


def fill_cache(cache, texts_by_sha, embed=None):
    """캐시에 없는 본문(texts_by_sha: sha → 본문)을 BATCH개씩 임베딩해 캐시에 붙이고 새로 만든 본문 수를 돌려준다."""
    # embed: 본문 목록 → 벡터 목록. 비우면 embed_texts(text-embedding-3-small)를 쓴다
    # [주의] 한 묶음은 MAX_RETRY번까지 다시 부르고(EC-05), 그래도 실패하면 예외를 그대로 올린다
    if embed is None:
        from backend.services.llm import embed_texts

        def embed(texts):
            return embed_texts(texts)[0]
    todo = [s for s in texts_by_sha if s not in cache.index]
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        for attempt in range(1, MAX_RETRY + 1):
            try:
                vectors = embed([texts_by_sha[s] for s in part])
                break
            except Exception:
                if attempt == MAX_RETRY:
                    raise
                time.sleep(2 * attempt)
        if len(vectors) != len(part):  # [주의] 개수가 어긋난 채 붙이면 sha와 벡터 짝이 밀려 엉뚱한 본문에 벡터가 붙는다
            raise ValueError(f'임베딩 개수 {len(vectors)}개가 본문 {len(part)}개와 다르다')
        cache.add(list(zip(part, vectors)))
    return len(todo)


FILL_BITS = ('INSERT INTO chunk_embedding_bits (chunk_id, embedding_model, bits)'
             ' SELECT chunk_id, embedding_model, binary_quantize(embedding::vector(1024))::bit(1024)'
             ' FROM chunk_embeddings WHERE embedding_model = %s ON CONFLICT (chunk_id, embedding_model) DO NOTHING')


def fill_voyage(chunks_path, vec_dir):
    """chunks.jsonl 본문 중 voyage-4-large 캐시(<벡터 폴더>/v4large.*)에 없는 것만 임베딩해 붙인다(Voyage 유료 호출, DB 안 씀)."""
    # [왜] 청크를 다시 자르면 바뀐 본문만 새 벡터가 필요하다. 그대로인 본문은 sha가 같아 캐시를 다시 쓴다
    from backend.services.llm import voyage_embed
    with open(chunks_path, encoding='utf-8') as fh:
        texts = {c['sha256']: c['text'] for c in (json.loads(line) for line in fh if line.strip())}
    made = fill_cache(VectorCache(vec_dir, 'v4large', VOYAGE_DIM), texts, lambda t: voyage_embed(t, 'document'))
    print(f'새로 임베딩한 voyage-4-large 본문 {made}개 / 서로 다른 본문 {len(texts)}개')


def load_voyage(vec_dir):
    """미리 만든 voyage-4-large 청크 벡터를 이미 들어간 청크에 붙이고 비트 코드 표도 채운다(DATABASE_URL 필요, 임베딩 API 호출 없음)."""
    # [주의] 벡터가 없는 청크가 하나라도 있으면 ValueError를 올려 아무것도 넣지 않는다
    import psycopg
    from pgvector.psycopg import register_vector
    from pgvector import HalfVector
    cache = VectorCache(vec_dir, 'v4large', VOYAGE_DIM)
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        register_vector(conn)
        cur = conn.cursor()
        actual = cur.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                             "WHERE attrelid='chunk_embeddings'::regclass AND attname='embedding'").fetchone()[0]
        if actual != 'halfvec':
            raise ValueError('embedding column must be dimensionless halfvec: apply db/008 first')
        cur.execute('SELECT dc.id, dc.chunk_sha256 FROM document_chunks dc WHERE NOT EXISTS (SELECT 1 FROM chunk_embeddings ce'
                    ' WHERE ce.chunk_id = dc.id AND ce.embedding_model = %s)', (VOYAGE_MODEL,))
        rows = [(cid, s.strip()) for cid, s in cur.fetchall()]
        if any(s not in cache.index for _, s in rows):
            raise ValueError('required voyage vectors are missing from the cache file')
        with cur.copy('COPY chunk_embeddings (chunk_id, embedding_model, embedding) FROM STDIN WITH (FORMAT BINARY)') as cp:
            cp.set_types(['int8', 'varchar', 'halfvec'])
            for chunk_id, s in rows:
                cp.write_row((chunk_id, VOYAGE_MODEL, HalfVector(cache.get(s))))
        # [왜] retrieve()의 dense 1단계(Hamming 후보 거르기)가 읽는 비트 표를 임베딩과 같이 채워 둔다(db/009와 같은 INSERT … SELECT)
        # [주의] 009를 아직 적용하지 않았으면 건너뛴다. 그 뒤 009를 적용하면 같은 문장이 비트를 채운다
        if cur.execute("SELECT to_regclass('chunk_embedding_bits')").fetchone()[0] is None:
            print('chunk_embedding_bits 표가 없어 비트 코드는 건너뜀(db/009 적용 필요)')
        else:
            cur.execute(FILL_BITS, (VOYAGE_MODEL,))
            print(f'넣은 비트 코드 {cur.rowcount}개')
    print(f'넣은 voyage-4-large 임베딩 {len(rows)}개')


def main(manifest_path, chunks_path, vec_dir, cache_only=False, chunks_only=False):
    """manifest·chunks.jsonl의 문서·청크·임베딩을 DB에 넣는다(DATABASE_URL 필요). 이미 있는 것은 건너뛴다."""
    # [주의] chunks_only면 문서·청크만 넣고 3-small 임베딩은 만들지도 넣지도 않는다(voyage는 --voyage로 따로 넣는다)
    # [주의] cache_only면 임베딩 API를 부르지 않고, 캐시에 없는 벡터가 필요하면 ValueError를 올려 DB를 롤백한다
    # [주의] RAG_VECTOR_TYPE과 DB 열 형식이 다르면 ValueError, 청크 파일이 DB와 다르면 SystemExit
    import psycopg
    from pgvector.psycopg import register_vector
    from pgvector import HalfVector
    kind = vector_type()
    # manifest에 없는 공통 값은 chunk.py의 DOC_DEFAULTS로 채우고, 줄에 적힌 값이 앞선다.
    with open(manifest_path, encoding='utf-8') as fh:
        docs = [{**DOC_DEFAULTS, **json.loads(line)} for line in fh if line.strip()]
    with open(chunks_path, encoding='utf-8') as fh:
        cards = [json.loads(line) for line in fh if line.strip()]
    cache = VectorCache(vec_dir)
    texts = {c['sha256']: c['text'] for c in cards}
    # 문서 키 → 분류. 한 문서의 카드는 모두 같은 category를 갖는다(chunks-v4h 1,360문서 확인)
    # [왜] 사양 표 없이 찾는 코드가 part_specifications.category와 같은 값으로 거르게 specs.py의 family()를 그대로 쓴다('tvs-18' → 'tvs')
    # [주의] 분류가 없는 카드면 빈 글자 대신 NULL을 넣는다
    category = {doc_key(c['doc']): family(c.get('category')) or None for c in cards}
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:  # with: 오류 없이 끝나면 커밋, 예외면 롤백한다
        register_vector(conn)
        cur = conn.cursor()
        actual = cur.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                             "WHERE attrelid='chunk_embeddings'::regclass AND attname='embedding'").fetchone()[0]
        if actual not in (f'{kind}({DIM})', kind):  # 차원 없는 halfvec(db/008)도 받는다
            raise ValueError('RAG_VECTOR_TYPE and database embedding type do not match')
        for d in docs:  # 문서: 이미 있으면 건너뛴다
            cur.execute(
                'INSERT INTO source_documents (document_key, document_type, title, publisher, source_url, revision, license_text,'
                ' file_sha256, corpus_version, collected_at, parser, chars_original, chars_kept, truncated, category)'
                ' VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (document_key) DO NOTHING',
                (d['doc_id'], 'DATASHEET', d['title'], d['manufacturer'], d['source_url'], d['revision'], d['usage_conditions'],
                 d['sha256'], CORPUS_VERSION, d['collected_at'], d['parser'], d['chars_original'], d['chars_kept'], d['truncated'],
                 category.get(d['doc_id'])))
        cur.execute('SELECT document_key, id FROM source_documents')
        doc_id = dict(cur.fetchall())
        cur.execute('SELECT DISTINCT document_id FROM document_chunks')
        done = {r[0] for r in cur.fetchall()}
        # 청크: 청크가 하나도 없는 문서만 넣는다(문서 단위로 다 넣거나 안 넣거나)
        with cur.copy('COPY document_chunks (document_id, chunk_index, content, chunk_sha256, page_number,'
                      ' table_name, row_label, chunker_version) FROM STDIN') as cp:
            for c in cards:
                if doc_id[doc_key(c['doc'])] not in done:
                    # [주의] 면책 문구 같은 긴 첫 칸이 행 이름이 되는 표가 있다. 이름표 열만 자르고 본문(content)은 그대로 둔다
                    cp.write_row((doc_id[doc_key(c['doc'])], c['idx'], c['text'], c['sha256'], c['page'],
                                  c['table'] and c['table'][:LABEL_MAX], c['row'] and c['row'][:LABEL_MAX], CHUNKER_VERSION))
        if chunks_only:  # [왜] 서비스 검색은 voyage-4-large만 쓴다(ADR 0004 갱신). 3-small 벡터는 돈만 들고 쓰지 않는다
            for t in ('source_documents', 'document_chunks'):
                print(t, cur.execute(f'SELECT count(*) FROM {t}').fetchone()[0])
            return
        # 임베딩: 이 모델의 임베딩이 없는 청크만 넣는다
        cur.execute('SELECT dc.id, dc.chunk_sha256 FROM document_chunks dc WHERE NOT EXISTS (SELECT 1 FROM chunk_embeddings ce'
                    ' WHERE ce.chunk_id = dc.id AND ce.embedding_model = %s)', (EMBED_MODEL,))
        rows = [(cid, s.strip()) for cid, s in cur.fetchall()]
        # [왜] 임베딩이 없는 청크의 본문만 캐시에 채운다. 캐시를 잃어도 DB에 이미 있는 임베딩은 다시 부르지 않는다
        unknown = {s for _, s in rows if s not in texts}
        if unknown:
            raise SystemExit(f'청크 파일에 없는 본문 해시 {len(unknown)}개: DB와 같은 chunks.jsonl을 주세요')
        if cache_only and any(s not in cache.index for _, s in rows):
            raise ValueError('cache-only: required vectors are missing; embedding API was not called')
        made = fill_cache(cache, {s: texts[s] for _, s in rows})
        with cur.copy('COPY chunk_embeddings (chunk_id, embedding_model, embedding) FROM STDIN WITH (FORMAT BINARY)') as cp:
            cp.set_types(['int8', 'varchar', kind])  # DB 열과 이진 COPY의 저장 형식을 함께 맞춘다
            for chunk_id, s in rows:
                vector = cache.get(s)
                cp.write_row((chunk_id, EMBED_MODEL, HalfVector(vector) if kind == 'halfvec' else vector))
        cur.execute("SELECT to_regclass('ix_chunk_embeddings_hnsw')")
        if rows and cur.fetchone()[0] is not None:
            # [왜] 빈 표에 만든 HNSW 인덱스에 5만 행을 한꺼번에 넣으면 그래프가 나빠져 가까운 청크를 놓친다(11-01 실측:
            # 정확 검색 거리 0.345 청크를 놓치고 0.436 청크를 1위로 냄). 다 넣은 뒤 인덱스를 다시 만든다
            cur.execute("SET LOCAL maintenance_work_mem = '512MB'")
            cur.execute('REINDEX INDEX ix_chunk_embeddings_hnsw')
        for t in ('source_documents', 'document_chunks', 'chunk_embeddings'):
            cur.execute(f'SELECT count(*) FROM {t}')
            print(t, cur.fetchone()[0])
    print(f'새로 임베딩한 본문 {made}개, 이번에 넣은 임베딩 {len(rows)}개')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--voyage':
        sys.exit(load_voyage(sys.argv[2]))
    if len(sys.argv) == 4 and sys.argv[1] == '--voyage-fill':
        sys.exit(fill_voyage(sys.argv[2], sys.argv[3]))
    flag = sys.argv[4] if len(sys.argv) == 5 else None
    if len(sys.argv) != 4 and flag not in ('--cache-only', '--chunks-only'):
        sys.exit(__doc__)
    main(*sys.argv[1:4], cache_only=flag == '--cache-only', chunks_only=flag == '--chunks-only')
