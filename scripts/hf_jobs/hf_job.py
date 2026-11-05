# /// script
# dependencies = ["sentence-transformers>=3.0", "huggingface_hub>=0.34", "numpy"]
# ///
# HF Jobs에서 GPU 임베딩 모델로 카드(문서 쪽)와 질의(질문 쪽)를 임베딩해 같은 비공개 데이터셋 저장소의 out/<키>/에 올린다.
# 하지 않는 일: 검색·채점(run_retrieval_layers.py), 공개 업로드. 저장소는 scripts/hf_jobs/hf_data.py pack이 비공개로 만든 것만 쓴다.
# 근거: docs/research/retrieval-layered-rerun-2026-11-03.md 3층(미룬 GPU 모델), evals/runners/embed_cards.py(질문 쪽 규칙: Qwen만 QWEN_QUERY_PROMPT, 정규화)
# 실행(맥에서): hf jobs uv run --flavor t4-small --timeout 45m --secrets HF_TOKEN scripts/hf_jobs/hf_job.py <저장소> kure qwen06 bgem3
import json
import os
import sys
import time

import numpy as np
import torch
from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from sentence_transformers import SentenceTransformer

# revision이 있으면 11-02와 같은 가중치, 없으면 작업 시작 때 main의 커밋을 받아 기록한다
MODELS = {
    'kure': {'name': 'nlpai-lab/KURE-v1', 'revision': '8b418a58414668e75532ed045c22d9ca018ae2b2', 'bs': 64},
    'qwen06': {'name': 'Qwen/Qwen3-Embedding-0.6B', 'revision': '97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3', 'bs': 64},
    'bgem3': {'name': 'BAAI/bge-m3', 'revision': None, 'bs': 64},
    'qwen4b': {'name': 'Qwen/Qwen3-Embedding-4B', 'revision': None, 'bs': 16},
    'qwen8b': {'name': 'Qwen/Qwen3-Embedding-8B', 'revision': None, 'bs': 8},
}


def main(repo, keys):
    token = os.environ['HF_TOKEN']  # [주의] --secrets HF_TOKEN으로 받은 값. 찍지 않는다
    api = HfApi(token=token)
    get = lambda f: hf_hub_download(repo, f, repo_type='dataset', token=token)  # noqa: E731
    cards = [json.loads(l) for l in open(get('cards.jsonl'), encoding='utf-8')]
    queries = [json.loads(l) for l in open(get('queries.jsonl'), encoding='utf-8')]
    meta = json.load(open(get('meta.json'), encoding='utf-8'))
    # [왜] T4(연산 능력 7.5)는 bf16을 흉내만 내서 느리다(11-03 시험: KURE 23장/초). 8 미만이면 fp16, A10G는 bf16
    dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
    order = sorted(range(len(cards)), key=lambda i: len(cards[i]['text']))  # 길이순으로 묶어 패딩을 줄인다(embed.py와 같음)
    for key in keys:
        m = MODELS[key]
        rev = m['revision'] or api.model_info(m['name']).sha
        t0 = time.time()
        model = SentenceTransformer(snapshot_download(m['name'], revision=rev, token=token), device='cuda',
                                    model_kwargs={'torch_dtype': dtype})
        model.max_seq_length = min(model.max_seq_length, 1024)  # 카드 최장 1,980자라 1,024토큰이면 잘리지 않는다
        load_sec = time.time() - t0
        t1 = time.time()
        V = model.encode([cards[i]['text'] for i in order], batch_size=m['bs'], normalize_embeddings=True,
                         convert_to_numpy=True, show_progress_bar=False)
        doc_sec = time.time() - t1
        used = dtype
        if not np.isfinite(V).all():  # [주의] fp16 넘침(NaN)이면 float32로 다시 계산한다
            used = torch.float32
            model = model.to(torch.float32)
            V = model.encode([cards[i]['text'] for i in order], batch_size=m['bs'], normalize_embeddings=True,
                             convert_to_numpy=True, show_progress_bar=False)
            doc_sec = time.time() - t1
        docs = np.empty_like(V)
        docs[order] = V  # 원래 카드 순서로 되돌린다
        prompt = meta['qwen_query_prompt'] if key.startswith('qwen') else None
        Q = model.encode([q['text'] for q in queries], prompt=prompt, batch_size=16, normalize_embeddings=True,
                         convert_to_numpy=True, show_progress_bar=False)
        out = f'/tmp/out/{key}'
        os.makedirs(out, exist_ok=True)
        docs.astype(np.float32).tofile(f'{out}/cards.f32')
        Q.astype(np.float32).tofile(f'{out}/queries.f32')
        log = {'model': m['name'], 'revision': rev, 'gpu': torch.cuda.get_device_name(0), 'dtype': str(used),
               'cards': len(cards), 'queries': len(queries), 'dim': int(V.shape[1]), 'batch_size': m['bs'],
               'load_sec': round(load_sec, 1), 'doc_sec': round(doc_sec, 1),
               'cards_per_sec': round(len(cards) / doc_sec, 1), 'query_prompt': bool(prompt)}
        json.dump(log, open(f'{out}/log.json', 'w'), indent=1)
        api.upload_folder(repo_id=repo, repo_type='dataset', folder_path=out, path_in_repo=f'out/{key}')
        print(json.dumps(log), flush=True)
        del model
        torch.cuda.empty_cache()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
