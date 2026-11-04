# HF Jobs용 데이터 주고받기(맥). pack: 카드·질의 글을 비공개 데이터셋 저장소에 올린다. fetch: 결과 벡터를 받아 검증하고
# vectors/<키>.f32·.sha.txt, inputs/qvec_<키>.npz로 바꾼다. delete: 검증이 끝난 뒤 저장소를 지운다.
# 하지 않는 일: 공개 업로드(TSC 이용 조건상 재배포 금지라 비공개가 아니면 멈춘다), 토큰 읽기·출력(hf auth login 로그인을 그대로 쓴다).
# 근거: docs/research/retrieval-layered-rerun-2026-11-03.md 3층, hf_job.py, 레포 evals/runners/benchmark_embeddings.py(QWEN_QUERY_PROMPT)
# 실행(저장소 루트): uv run --no-project --with huggingface_hub --with numpy python scripts/hf_jobs/hf_data.py <명령> ...
#   입출력 폴더는 LAYERS_WORK(기본 ../전자_데이터시트/evidence/full_grid), 결과는 run_retrieval_layers.py가 읽는다
#   pack trial|full <기대 계정> | fetch <저장소> <키> [trial] | delete <저장소>
import ast
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from huggingface_hub import HfApi, snapshot_download

HERE = Path(os.environ.get('LAYERS_WORK', '../전자_데이터시트/evidence/full_grid'))  # run_retrieval_layers.py와 같은 작업 폴더
ROOT = HERE.parents[2]  # 코퍼스(corpus/tsc)가 있는 SojaFit 프로젝트 폴더(기본값이면 저장소의 바로 위 폴더 ..)
STAGE = Path(tempfile.gettempdir()) / 'sojafit_hf'  # 버릴 파일은 임시 폴더에
api = HfApi()


def distinct_cards():
    seen, out = set(), []
    for line in open(ROOT / 'corpus/tsc/chunks/chunks.jsonl', encoding='utf-8'):
        c = json.loads(line)
        if c['sha256'] not in seen:
            seen.add(c['sha256'])
            out.append({'sha': c['sha256'], 'text': c['text']})
    return out


def qwen_prompt():
    """레포의 QWEN_QUERY_PROMPT를 코드 실행 없이 글자 그대로 읽는다(11-02와 같은 질문 지시문)."""
    tree = ast.parse((ROOT / 'SojaFit/evals/benchmark_embeddings.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'QWEN_QUERY_PROMPT')
    return ast.literal_eval(node.value)


def pack(mode, expect_user):
    user = api.whoami()['name']
    if user != expect_user:
        raise SystemExit(f'로그인 계정 {user}이 기대한 {expect_user}가 아니어서 멈춘다')
    cards = distinct_cards()
    assert len(cards) == 45_898, len(cards)
    if mode == 'trial':  # [왜] 길이가 고르게 섞인 1,000장으로 속도를 재야 전체 시간을 어림할 수 있다
        pick = np.sort(np.random.default_rng(0).choice(len(cards), 1000, replace=False))
        cards = [cards[i] for i in pick]
    queries = [json.loads(l) for l in open(HERE / 'inputs/query_texts.jsonl', encoding='utf-8')]
    STAGE.mkdir(parents=True, exist_ok=True)
    with open(STAGE / 'cards.jsonl', 'w', encoding='utf-8') as f:
        f.writelines(json.dumps(c, ensure_ascii=False) + '\n' for c in cards)
    with open(STAGE / 'queries.jsonl', 'w', encoding='utf-8') as f:
        f.writelines(json.dumps(q, ensure_ascii=False) + '\n' for q in queries)
    json.dump({'mode': mode, 'cards': len(cards), 'queries': len(queries), 'qwen_query_prompt': qwen_prompt(),
               'created': time.strftime('%Y-%m-%dT%H:%M:%S')}, open(STAGE / 'meta.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    repo = f'{user}/sojafit-tsc-embed-{mode}'
    api.create_repo(repo, repo_type='dataset', private=True, exist_ok=True)
    if not api.repo_info(repo, repo_type='dataset').private:
        raise SystemExit(f'{repo}가 비공개가 아니어서 올리지 않는다')
    api.upload_folder(repo_id=repo, repo_type='dataset', folder_path=STAGE,
                      allow_patterns=['cards.jsonl', 'queries.jsonl', 'meta.json'])
    print(f'{repo}(비공개) 카드 {len(cards)}장, 질의 {len(queries)}개 올림')


def fetch(repo, key, trial=False):
    """결과를 받아 행 수·노름·NaN을 확인한다. 본 실행이면 run_retrieval_layers.py가 읽는 파일로 바꾼다."""
    path = Path(snapshot_download(repo, repo_type='dataset', allow_patterns=['cards.jsonl', 'queries.jsonl', f'out/{key}/*']))
    log = json.load(open(path / f'out/{key}/log.json'))
    cards = [json.loads(l)['sha'] for l in open(path / 'cards.jsonl', encoding='utf-8')]
    queries = [json.loads(l)['sha'] for l in open(path / 'queries.jsonl', encoding='utf-8')]
    D = np.fromfile(path / f'out/{key}/cards.f32', np.float32).reshape(-1, log['dim'])
    Q = np.fromfile(path / f'out/{key}/queries.f32', np.float32).reshape(-1, log['dim'])
    norms = np.linalg.norm(np.vstack([D, Q]), axis=1)
    ok = len(D) == len(cards) and len(Q) == len(queries) and np.isfinite(norms).all() and abs(norms - 1).max() < 1e-2
    print(key, 'OK' if ok else 'FAIL', f'카드 {len(D)}/{len(cards)} 질의 {len(Q)}/{len(queries)} 노름 {norms.min():.4f}~{norms.max():.4f}',
          json.dumps({k: log[k] for k in ('revision', 'gpu', 'dtype', 'load_sec', 'doc_sec', 'cards_per_sec')}))
    if not ok:
        raise SystemExit('검증 실패: 파일을 바꾸지 않는다')
    if trial:
        return
    (HERE / 'vectors').mkdir(exist_ok=True)
    D.tofile(HERE / f'vectors/{key}.f32')
    (HERE / f'vectors/{key}.sha.txt').write_text(''.join(s + '\n' for s in cards))
    json.dump(log, open(HERE / f'vectors/{key}.log.json', 'w'), indent=1)
    np.savez(HERE / f'inputs/qvec_{key}.npz', **{s[:20]: v for s, v in zip(queries, Q)})  # run_retrieval_layers.py와 같은 키(sha 앞 20자)


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'pack':
        pack(*args)
    elif cmd == 'fetch':
        fetch(args[0], args[1], trial=len(args) > 2)
    elif cmd == 'delete':
        api.delete_repo(args[0], repo_type='dataset')
        print(args[0], '지움')
    else:
        sys.exit('pack trial|full <계정> | fetch <저장소> <키> [trial] | delete <저장소>')
