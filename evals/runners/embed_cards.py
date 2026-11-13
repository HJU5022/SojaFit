"""임베딩 격자 본평가(evals/guides/preregister.md #16)의 카드 적재와 모델별 카드 임베딩(실험용).

- 하는 일
  - load: chunks.jsonl 카드 52,244장을 실험 DB(앱 DB와 별개)의 cards 표에 넣는다. 본문 sha256을 다시 계산해 맞춰 본다.
  - <모델 키>: 서로 다른 본문 45,898개를 그 모델로 새로 임베딩해 emb_<키> 표에 카드마다 넣는다. 기존 캐시 벡터는 쓰지 않는다.
    끊기면 다시 돌려 이어서 한다(이미 들어간 카드는 건너뜀). 시간·토큰·revision을 logs/embed_<키>.json에 남긴다.
  - embed(key, texts, kind): run_embedding_grid.py가 질문을 같은 방식으로 임베딩할 때 쓴다(kind='query' 또는 'document').
- 하지 않는 일: 검색·채점(run_embedding_grid.py)
- 출처: evals/guides/preregister.md #16, backend/services/llm.py(embed_texts), evals/runners/benchmark_embeddings.py(QWEN_QUERY_PROMPT)

실행(`evals/docker/Dockerfile.embedding_grid` 컨테이너, 저장소를 /work/repo에 두고 /work/data·/work/logs를 마운트, EMBED_DB에 실험 DB 주소):
  cd /work/repo && python -m evals.runners.embed_cards load /work/data/chunks.jsonl  |  python -m evals.runners.embed_cards <모델 키>
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from evals.runners.benchmark_embeddings import QWEN_QUERY_PROMPT  # noqa: E402  저장소와 같은 Qwen 질문 지시문

DB = os.environ.get('EMBED_DB')  # [왜] 접속 문자열은 코드에 적지 않는다(AGENTS 4). 비우면 psycopg가 PG* 환경변수를 읽는다
MODELS = {
    'te3s': {'kind': 'repo', 'name': 'openai/text-embedding-3-small', 'dim': 1536, 'max_tokens': 300_000},
    'kure': {'kind': 'st', 'name': 'nlpai-lab/KURE-v1', 'dim': 1024, 'revision': '8b418a58414668e75532ed045c22d9ca018ae2b2'},
    'qwen': {'kind': 'st', 'name': 'Qwen/Qwen3-Embedding-0.6B', 'dim': 1024,
             'revision': '97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3'},
    'v4lite': {'kind': 'voyage', 'name': 'voyage-4-lite', 'dim': 1024, 'max_tokens': 1_000_000},
    'v4': {'kind': 'voyage', 'name': 'voyage-4', 'dim': 1024, 'max_tokens': 320_000},
    'v4large': {'kind': 'voyage', 'name': 'voyage-4-large', 'dim': 1024, 'max_tokens': 120_000},
}
BATCH = 128  # API 한 번에 보내는 본문 수(ingest.py와 같음)
ST_BLOCK = 4096  # 로컬 모델은 이만큼씩 인코딩하고 DB에 넣는다(끊겨도 이어서 하려고)
MAX_RETRY = 5  # [왜] 키 한도가 있어 실패한 묶음을 끝없이 다시 부르지 않는다(AGENTS 6)
_st = {}


def _retry(call):
    for attempt in range(MAX_RETRY):
        try:
            return call()
        except Exception as e:  # noqa: BLE001  429·일시 오류를 같은 상한으로 다시 시도
            if attempt == MAX_RETRY - 1:
                raise
            print(f'retry {attempt + 1}: {type(e).__name__}: {str(e)[:200]}', flush=True)
            time.sleep(5 * 2 ** attempt)


def _sentence_model(key):
    if key not in _st:
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer
        m = MODELS[key]
        # [왜] 고정 revision의 로컬 경로로 불러 모델 정보 조회 없이 같은 가중치를 쓴다
        path = snapshot_download(m['name'], revision=m['revision'])
        _st[key] = SentenceTransformer(path, device='cuda')
    return _st[key]


def embed(key, texts, kind):
    """texts를 key 모델로 임베딩해 (float32 행렬, 토큰 수)를 돌려준다. 로컬 모델의 토큰 수는 0."""
    m = MODELS[key]
    if m['kind'] == 'repo':
        from backend.services.llm import embed_texts  # [왜] 서비스와 같은 호출 경로(AGENTS 2)
        vecs, tokens, _, _ = _retry(lambda: embed_texts(texts))
        return np.asarray(vecs, np.float32), tokens
    if m['kind'] == 'voyage':
        import voyageai
        r = _retry(lambda: voyageai.Client(max_retries=0).embed(
            texts, model=m['name'], input_type=kind, output_dimension=m['dim'], truncation=True))
        return np.asarray(r.embeddings, np.float32), r.total_tokens
    prompt = QWEN_QUERY_PROMPT if key == 'qwen' and kind == 'query' else None
    vecs = _sentence_model(key).encode(texts, prompt=prompt, batch_size=64, normalize_embeddings=True,
                                       convert_to_numpy=True, show_progress_bar=False)
    return vecs.astype(np.float32), 0


def batches(shas, text, m):
    """API 한도(본문 수·요청당 토큰)를 넘지 않게 sha를 묶는다. 토큰은 글자 수 / 2로 넉넉히 어림한다."""
    if m['kind'] == 'st':
        yield from (shas[i:i + ST_BLOCK] for i in range(0, len(shas), ST_BLOCK))
        return
    part, size = [], 0
    for s in shas:
        n = len(text[s]) // 2 + 1
        if part and (len(part) == BATCH or size + n > m['max_tokens'] // 2):
            yield part
            part, size = [], 0
        part.append(s)
        size += n
    if part:
        yield part


def load(chunks_path):
    cards = [json.loads(line) for line in open(chunks_path, encoding='utf-8')]
    bad = [i for i, c in enumerate(cards) if hashlib.sha256(c['text'].encode()).hexdigest() != c['sha256']]
    if bad:
        raise SystemExit(f'본문 sha256이 맞지 않는 카드 {len(bad)}장: {bad[:5]}')
    with psycopg.connect(DB) as conn:
        conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
        conn.execute('CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY, doc TEXT NOT NULL, page INTEGER,'
                     ' sha TEXT NOT NULL, text TEXT NOT NULL)')
        if conn.execute('SELECT count(*) FROM cards').fetchone()[0]:
            raise SystemExit('cards 표가 이미 차 있습니다')
        with conn.cursor().copy('COPY cards (id, doc, page, sha, text) FROM STDIN') as cp:
            for i, c in enumerate(cards):
                cp.write_row((i, c['doc'], c['page'], c['sha256'], c['text']))
    print(f'카드 {len(cards)}장, 서로 다른 본문 {len({c["sha256"] for c in cards})}개')


def embed_model(key):
    m = MODELS[key]
    log_path = f'/work/logs/embed_{key}.json'
    log = json.load(open(log_path)) if os.path.exists(log_path) else {'model': m['name'], 'dim': m['dim'], 'runs': []}
    with psycopg.connect(DB) as conn:
        register_vector(conn)
        conn.execute(f'CREATE TABLE IF NOT EXISTS emb_{key} (card_id INTEGER PRIMARY KEY REFERENCES cards (id),'
                     f' embedding vector({m["dim"]}) NOT NULL)')
        conn.commit()
        rows = conn.execute(f'SELECT c.id, c.sha, c.text FROM cards c WHERE NOT EXISTS'
                            f' (SELECT 1 FROM emb_{key} e WHERE e.card_id = c.id) ORDER BY c.id').fetchall()
        ids, text = {}, {}
        for i, s, t in rows:
            ids.setdefault(s, []).append(i)
            text[s] = t
        # [왜] 길이순으로 묶으면 한 묶음 안의 패딩이 줄어 로컬 모델이 빨라진다(11-01 embed_remote.py와 같음)
        shas = sorted(text, key=lambda s: len(text[s]))
        run = {'started': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'bodies': len(shas), 'cards': len(rows), 'tokens': 0}
        if m['kind'] == 'st':
            run['revision'] = m['revision']
            t0 = time.perf_counter()
            _sentence_model(key)
            run['load_sec'] = round(time.perf_counter() - t0, 1)
            import torch
            run['gpu'] = torch.cuda.get_device_name(0)
        t0, done = time.perf_counter(), 0
        for part in batches(shas, text, m):
            vecs, n = embed(key, [text[s] for s in part], 'document')
            if vecs.shape != (len(part), m['dim']):
                raise ValueError(f'벡터 모양이 다릅니다: {vecs.shape}')
            with conn.cursor().copy(f'COPY emb_{key} (card_id, embedding) FROM STDIN WITH (FORMAT BINARY)') as cp:
                cp.set_types(['int4', 'vector'])
                for s, v in zip(part, vecs):
                    for i in ids[s]:
                        cp.write_row((i, v))
            conn.commit()
            run['tokens'] += n
            done += len(part)
            print(f'{key} {done}/{len(shas)} {time.perf_counter() - t0:.0f}s tokens={run["tokens"]}', flush=True)
        run['embed_sec'] = round(time.perf_counter() - t0, 1)
        run['finished'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        run['table_rows'] = conn.execute(f'SELECT count(*) FROM emb_{key}').fetchone()[0]
    log['runs'].append(run)
    json.dump(log, open(log_path, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(run, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'load':
        load(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] in MODELS:
        embed_model(sys.argv[1])
    else:
        sys.exit(__doc__)
