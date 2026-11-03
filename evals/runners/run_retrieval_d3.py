"""D3 공식 검색 측정(사전 등록 #24): 동결 v2의 채점 19문항을 쪽 단위 정답(qrels)으로, 한 번에 한 조건만 바꿔 잰다.

- 하는 일
  - qrels: v2 gold 줄에 적힌 모든 쪽을 (PDF, 쪽)으로 풀어 evals/inputs/qrels_v2_pages.json을 만든다(카드 없는 쪽은 회수 불가로 표시).
  - official: 기준(서비스 경로) 하나와 E1~E8 칸을 재고, 칸마다 필터 끔으로도 다시 잰다. 결과·문항별 원시 순위를 json으로 남긴다.
  - noresult: 관련 19 · 비관련 35문항의 1위 점수 분포(no_result 임계값, 1주 16강).
  - chunks / embed: E6 청킹 변형(쪽마다 고정 길이 · 겹침, 의미 단위)을 만들고 3-small로 임베딩한다.
  - explore: 공식 측정 뒤 탐색 격자(임베딩 × 리랭커 × 질의 × 방식 × 필터). 결과에 "탐색"으로 표시한다.
- 하지 않는 일: 평가셋 수정, 서비스 코드 수정, 답변 채점. 카드·벡터는 저장소 밖 파일을 인자로 읽는다(용량).
- 출처: evals/guides/preregister.md #24, backend/rag/retrieve.py(tokens·rrf·positive_top·part_index·allowed_chunks),
  backend/graph/nodes.py(find_parts·read_input·search의 필터 규칙), 1주 03·05·06·09·12·13·14·16·18·19강, 특강 08강
- 실행(저장소 루트): uv run --with docling-core python -m evals.runners.run_retrieval_d3 <명령> [옵션]
  명령: qrels | official | noresult | chunks | embed <이름> | explore. 옵션은 --help
- [주의] Voyage 리랭크는 이 실행기에서 REST로 부른다(임베딩·LLM이 아니라 서비스 경계 밖의 평가 전용 호출). 무료 한도만 쓰고 결제 신호가 오면 멈춘다.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / 'evals/dataset_v2.jsonl'
V2_SHA = '81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9'
QRELS = ROOT / 'evals/inputs/qrels_v2_pages.json'
REWRITE = ROOT / 'evals/inputs/rewrite_q3_v2.json'
OUTSIDE = ROOT.parent  # 저장소 밖 프로젝트 폴더(카드·벡터)
KS = (1, 3, 5, 10)
PAGE_TOKEN = re.compile(r'([^;,]*?\.pdf)|(\d+(?:\s*[~∼·-]\s*\d+)*)\s*쪽')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def jdump(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


# ---------- qrels ----------
def gold_pages(line):
    """gold 한 줄의 (PDF, 쪽) 전부. 'A.pdf, 1쪽 …; 2쪽 …'처럼 PDF 뒤에 이어 적은 쪽과 '2~3쪽' 범위도 센다."""
    out, cur = [], None
    for m in PAGE_TOKEN.finditer(line):
        if m.group(1):
            cur = m.group(1).strip()
        elif cur:
            nums = [int(x) for x in re.findall(r'\d+', m.group(2))]
            if re.search(r'[~∼-]', m.group(2)) and len(nums) == 2:
                nums = list(range(nums[0], nums[1] + 1))
            out += [(cur, p) for p in nums]
    return list(dict.fromkeys(out))


def load_v2():
    raw = V2.read_bytes()
    if hashlib.sha256(raw).hexdigest() != V2_SHA:
        raise SystemExit('dataset_v2.jsonl sha256이 동결 값과 달라 멈춘다')
    return [json.loads(l) for l in raw.decode('utf-8').splitlines() if l.strip()]


def scored(items):
    """채점 대상: 관련 · candidate_find 아님 · PDF gold 있음(사전 등록 #24, 19건)."""
    return [it for it in items if it['kind'] == 'relevant' and it.get('question_type') != 'candidate_find'
            and any(gold_pages(g) for g in it['gold_chunks'])]


def make_qrels(cards_path):
    items = scored(load_v2())
    have = Counter((c['doc'], c['page']) for c in map(json.loads, open(cards_path, encoding='utf-8')))
    q = {}
    for it in items:
        pages = list(dict.fromkeys(p for g in it['gold_chunks'] for p in gold_pages(g)))
        q[it['id']] = {'pages': [list(p) for p in pages], 'unrecoverable': [list(p) for p in pages if not have[p]],
                       'pdf': pages[0][0]}
    meta = {'dataset_sha256': V2_SHA, 'cards_sha256': hashlib.sha256(Path(cards_path).read_bytes()).hexdigest(),
            'items': len(q), 'pages': sum(len(v['pages']) for v in q.values()),
            'unrecoverable': sum(len(v['unrecoverable']) for v in q.values())}
    jdump({'meta': meta, 'qrels': q}, QRELS)
    print(json.dumps(meta, ensure_ascii=False))


# ---------- 색인 ----------
class Index:
    """카드 묶음 하나(서비스 C 카드 또는 E6 변형)의 품번·분류·종류 필터와 키워드 색인."""

    def __init__(self, path, name):
        from backend.rag.retrieve import part_index
        self.name, self.cards = name, [json.loads(l) for l in open(path, encoding='utf-8')]
        self.ids = list(range(len(self.cards)))
        if any(c.get('kind') == 'cover' for c in self.cards):  # 서비스 카드: 표지 글에서 품번 → 문서
            self.part = part_index([(i, c['doc'], c['text']) for i, c in enumerate(self.cards)])
        else:  # [주의] 표지 카드가 없는 변형은 카드 메타데이터 parts로 같은 모양을 만든다
            pd, dc = {}, {}
            for i, c in enumerate(self.cards):
                dc.setdefault(c['doc'], []).append(i)
                for p in c.get('parts') or []:
                    pd.setdefault(p.lower(), set()).add(c['doc'])
            self.part = (pd, dc)
        self.nocover = {i for i, c in enumerate(self.cards) if c.get('kind') != 'cover'}
        self.by_cat = defaultdict(set)
        for i, c in enumerate(self.cards):
            self.by_cat[c['category']].add(i)
        self.have = Counter((c['doc'], c['page']) for c in self.cards)
        self._kw, self._masks = {}, {}

    def allowed(self, F, parts):
        from backend.rag.retrieve import allowed_chunks
        if F is None:
            return None
        part_ids = allowed_chunks(self.part, parts) if parts else None
        if F == 'part':
            return part_ids
        if F == 'category':
            return None if part_ids is None else set().union(*(self.by_cat[self.cards[i]['category']] for i in part_ids)) if part_ids else set()
        if F == 'kind':
            return self.nocover
        if F == 'part+kind':
            return self.nocover if part_ids is None else part_ids & self.nocover
        raise ValueError(F)

    def mask(self, allowed):
        import numpy as np
        key = frozenset(allowed)
        if key not in self._masks:
            m = np.zeros(len(self.cards), bool)
            m[list(allowed)] = True
            self._masks[key] = m
        return self._masks[key]

    def keyword(self, kind, T):
        """kind 'bm25'(BM25Okapi 기본값) 또는 'tfidf'(1주 03강 idf = log((N+1)/(df+1))+1, 코사인)."""
        if (kind, T) not in self._kw:
            docs = [TOK[T](c['text']) for c in self.cards]
            if kind == 'bm25':
                from rank_bm25 import BM25Okapi
                self._kw[kind, T] = BM25Okapi(docs)
            else:
                self._kw[kind, T] = TfIdf(docs)
        return self._kw[kind, T]


class TfIdf:
    """TF-IDF 코사인 검색. 낱말 → (카드, 정규화 가중치) 역색인으로 질문 낱말이 든 카드만 센다."""

    def __init__(self, docs):
        n = len(docs)
        df = Counter(t for d in docs for t in set(d))
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        self.post, self.n = defaultdict(list), n
        for i, d in enumerate(docs):
            w = {t: c * self.idf[t] for t, c in Counter(d).items()}
            norm = math.sqrt(sum(v * v for v in w.values())) or 1.0
            for t, v in w.items():
                self.post[t].append((i, v / norm))

    def get_scores(self, q):
        import numpy as np
        qw = {t: c * self.idf[t] for t, c in Counter(q).items() if t in self.idf}
        norm = math.sqrt(sum(v * v for v in qw.values())) or 1.0
        s = np.zeros(self.n)
        for t, v in qw.items():
            for i, dv in self.post[t]:
                s[i] += v / norm * dv
        return s


def t1(text):
    from backend.graph.nodes import QUANTITY, WORD
    from backend.rag.retrieve import tokens
    extra = []
    for w in WORD.findall(text):
        if QUANTITY.fullmatch(w):
            m = re.match(r'(\d+(?:\.\d+)?)([A-Za-z]{1,3})$', w)
            extra += [m.group(1), m.group(2).lower()]
    return tokens(text) + extra


def t2(text):
    from backend.rag.retrieve import tokens
    toks = tokens(text)
    mixed = [t for t in toks if re.search('[a-z]', t) and re.search(r'\d', t)]
    return toks + [t[:n] for t in mixed for n in range(4, len(t))]


def t3(text):
    from backend.rag.retrieve import tokens
    return [t[i:i + 2] for t in tokens(text) for i in range(max(len(t) - 1, 1))]


def t0(text):
    from backend.rag.retrieve import tokens
    return tokens(text)


TOK = {'T0': t0, 'T1': t1, 'T2': t2, 'T3': t3}


# ---------- 벡터 ----------
class Vectors:
    """모델별 카드 벡터(본문 sha 목록과 짝)와 질문 벡터 캐시(npz, 키는 질의 sha 앞 20자)."""

    def __init__(self, args):
        self.a, self.cache, self.q = args, {}, {}

    def files(self, model, index):
        if index.name != 'C':  # 변형 카드: 3-small은 <변형>.f32, 다른 모델은 <변형>.<모델>.f32(GPU 단계)
            tag = '' if model == 'te3s' else f'.{model}'
            return Path(self.a.chunk_dir) / f'{index.name}{tag}.f32', Path(self.a.chunk_dir) / f'{index.name}{tag}.sha.txt', None
        if model == 'te3s':
            return OUTSIDE / 'corpus/tsc/embeddings/vectors.f32', OUTSIDE / 'corpus/tsc/embeddings/vectors.sha.txt', 1536
        src = 'te3l' if model == 'te3l1536' else model
        dim = json.load(open(Path(self.a.vectors) / f'{src}.log.json')).get('dim') if (Path(self.a.vectors) / f'{src}.log.json').exists() else None
        return Path(self.a.vectors) / f'{src}.f32', Path(self.a.vectors) / f'{src}.sha.txt', dim

    def cards(self, model, index):
        import numpy as np
        key = (model, index.name)
        if key not in self.cache:
            f, s, dim = self.files(model, index)
            shas = open(s).read().split()
            V = np.fromfile(f, np.float32)
            V = V.reshape(len(shas), -1)
            if model == 'te3l1536':
                V = V[:, :1536]
            row = {h: i for i, h in enumerate(shas)}
            # [왜] late chunking 벡터는 같은 글이라도 앞뒤 문맥에 따라 달라 본문 sha가 아니라 카드 번호(card:<i>)로 짝짓는다
            rows = [row[f'card:{k}'] if f'card:{k}' in row else row[c['sha256']] for k, c in enumerate(index.cards)]
            self.cache[key] = (V / np.linalg.norm(V, axis=1, keepdims=True), np.array(rows))
        return self.cache[key]

    def query(self, model, text):
        import numpy as np
        src = {'te3l1536': 'te3l', 'bgem3late': 'bgem3'}.get(model, model)  # late chunking은 문서 쪽만 바뀌고 질문은 같은 모델
        if src not in self.q:
            p = Path(self.a.qvec_dir) / f'qvec_{src}.npz'
            self.q[src] = dict(np.load(p)) if p.exists() else {}
        k = sha(text)[:20]
        if k not in self.q[src]:
            if src != 'te3s':
                raise KeyError(f'{src} 질문 벡터 없음')
            from backend.services.llm import embed_texts  # [왜] 임베딩 호출은 서비스 경계 하나로(AGENTS 2)
            vecs, _, _, model_id = embed_texts([text])
            assert model_id.endswith('text-embedding-3-small'), model_id
            self.q[src][k] = np.asarray(vecs[0], np.float32)
            np.savez(Path(self.a.qvec_dir) / f'qvec_{src}.npz', **self.q[src])
        v = self.q[src][k]
        return v[:1536] if model == 'te3l1536' else v


# ---------- 리랭커 ----------
class Reranker:
    """Voyage rerank-3 · rerank-3-lite(REST) 또는 로컬 CrossEncoder(GPU 단계). 같은 (모델, 질의, 후보 sha)는 캐시에서 꺼낸다."""

    def __init__(self, path):
        self.path, self.cache, self.local, self.blocked = Path(path), {}, {}, False
        if self.path.exists():
            for line in open(self.path):
                r = json.loads(line)
                self.cache[r['key']] = r
        self.new_calls = self.new_tokens = 0

    def order(self, model, text, cands, index):
        if not cands:
            return []
        key = sha(json.dumps([model, text, [index.cards[c]['sha256'] for c in cands]]))
        if key not in self.cache:
            docs = [index.cards[c]['text'] for c in cands]
            if model.startswith('rerank-'):
                rec = self.voyage(model, text, docs)
            elif model.startswith('Qwen/Qwen3-Reranker'):
                rec = self.qwen3(model, text, docs)
            else:
                import numpy as np
                if model not in self.local:
                    from sentence_transformers import CrossEncoder
                    self.local[model] = CrossEncoder(model, max_length=1024)
                s = self.local[model].predict([(text, d) for d in docs], batch_size=16, show_progress_bar=False)
                rec = {'order': [int(i) for i in np.argsort(-np.asarray(s), kind='stable')], 'tokens': 0,
                       'scores': sorted((float(x) for x in s), reverse=True), 'method': 'sentence-transformers CrossEncoder(max_length=1024)'}
            rec['key'] = key
            with open(self.path, 'a') as f:
                f.write(json.dumps(rec) + '\n')
            self.cache[key] = rec
        return [cands[i] for i in self.cache[key]['order']]

    QWEN_INSTRUCTION = 'Given a web search query, retrieve relevant passages that answer the query'  # 모델 카드 기본 지시문
    QWEN_PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct '
                   'provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
    QWEN_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'

    def qwen3(self, model, text, docs):
        """Qwen3-Reranker 모델 카드 방식: 정해진 프롬프트로 다음 낱말이 yes일 확률(yes·no 로짓의 softmax)을 점수로 쓴다.
        [주의] CrossEncoder로 그냥 불러오면 분류 머리가 임의값이라 점수가 틀린다."""
        import numpy as np
        import torch
        if model not in self.local:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            tok = AutoTokenizer.from_pretrained(model, padding_side='left')
            lm = AutoModelForCausalLM.from_pretrained(model, torch_dtype=torch.bfloat16).cuda().eval()
            pre, suf = tok(self.QWEN_PREFIX, add_special_tokens=False)['input_ids'], tok(self.QWEN_SUFFIX, add_special_tokens=False)['input_ids']
            self.local[model] = (tok, lm, pre, suf, tok.convert_tokens_to_ids('yes'), tok.convert_tokens_to_ids('no'))
        tok, lm, pre, suf, yes, no = self.local[model]
        scores = []
        for i in range(0, len(docs), 8):
            pairs = [f'<Instruct>: {self.QWEN_INSTRUCTION}\n<Query>: {text}\n<Document>: {d}' for d in docs[i:i + 8]]
            enc = tok(pairs, padding=False, truncation='longest_first', return_attention_mask=False, max_length=4096 - len(pre) - len(suf))
            enc['input_ids'] = [pre + ids + suf for ids in enc['input_ids']]
            enc = tok.pad(enc, padding=True, return_tensors='pt').to('cuda')
            with torch.no_grad():
                last = lm(**enc).logits[:, -1, :]
            scores += torch.softmax(torch.stack([last[:, no], last[:, yes]], 1).float(), 1)[:, 1].tolist()
        return {'order': [int(i) for i in np.argsort(-np.asarray(scores), kind='stable')], 'tokens': 0,
                'scores': sorted(scores, reverse=True), 'method': 'Qwen3-Reranker 모델 카드 yes/no 로짓(bf16, max_length 4096)',
                'instruction': self.QWEN_INSTRUCTION}

    def voyage(self, model, text, docs):
        import httpx
        if self.blocked:
            raise RuntimeError('Voyage 결제 신호 뒤라 건너뛴다')
        if not os.getenv('VOYAGE_API_KEY'):
            raise RuntimeError('캐시에 없는 Voyage 칸이고 키가 없어 부르지 않는다')
        for attempt in range(5):
            r = httpx.post('https://api.voyageai.com/v1/rerank', timeout=180,
                           headers={'Authorization': f'Bearer {os.environ["VOYAGE_API_KEY"]}'},
                           json={'query': text, 'documents': docs, 'model': model, 'truncation': True})
            if r.status_code == 200:
                d = r.json()
                self.new_calls += 1
                self.new_tokens += d['usage']['total_tokens']
                return {'order': [x['index'] for x in d['data']], 'scores': [x['relevance_score'] for x in d['data']],
                        'tokens': d['usage']['total_tokens']}
            if r.status_code == 402 or re.search('payment|billing', r.text, re.I):
                self.blocked = True
                raise RuntimeError(f'Voyage 결제 신호 {r.status_code}')
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(5 * 2 ** attempt)
                continue
            raise RuntimeError(f'Voyage 오류 {r.status_code}')


# ---------- 검색 ----------
BASE = {'model': 'te3s', 'S': 'hybrid', 'kw': 'bm25', 'T': 'T0', 'rrf_k': 60, 'n': 50, 'Q': 'Q2', 'F': 'part',
        'rerank': None, 'chunk': 'C'}  # 서비스 경로(사전 등록 #24 기준)


def name(cfg):
    return '|'.join(str(cfg[k]) for k in ('chunk', 'model', 'S', 'kw', 'T', 'rrf_k', 'n', 'Q', 'F', 'rerank'))


def search(cfg, q, ctx):
    """서비스 retrieve()와 같은 순서: 필터 → dense·키워드 후보 → RRF → (리랭크). 동점은 카드 순서로 고정한다."""
    import numpy as np
    from backend.rag import retrieve as R
    index = ctx['index'][cfg['chunk']]
    text = q['text'][cfg['Q']]
    allowed = index.allowed(cfg['F'], q['parts'])
    rec = {'allowed': None if allowed is None else len(allowed)}
    if allowed is not None and not allowed:
        return [], set(), allowed, {**rec, 'empty': True}
    dense, kw, dscore, kscore = [], [], {}, {}
    if cfg['S'] in ('dense', 'hybrid'):
        Vn, row = ctx['vec'].cards(cfg['model'], index)
        qv = ctx['vec'].query(cfg['model'], text)
        sim = (Vn @ (qv / np.linalg.norm(qv)))[row]
        if allowed is not None:
            sim = np.where(index.mask(allowed), sim, -np.inf)
        order = np.lexsort((np.arange(len(sim)), -sim))[:cfg['n']]  # [왜] 거리 → 카드 순서로 동점을 고정
        dense = [int(j) for j in order if np.isfinite(sim[j])]
        dscore = {j: float(sim[j]) for j in dense}
        rec['dense_tie_at_5'] = len(dense) > 5 and dscore[dense[4]] == dscore[dense[5]]
    if cfg['S'] in ('bm25', 'hybrid'):
        s = index.keyword(cfg['kw'], cfg['T']).get_scores(TOK[cfg['T']](text))
        if allowed is not None:
            s = np.where(index.mask(allowed), s, -np.inf)
        kw = R.positive_top(s, index.ids, cfg['n'])
        kscore = {j: float(s[j]) for j in kw}
        rec['kw_tie_at_5'] = len(kw) > 5 and kscore[kw[4]] == kscore[kw[5]]
    R.RRF_K = cfg['rrf_k']  # [왜] 레포 rrf()가 모듈 상수를 읽어 칸마다 바꿨다가 되돌린다
    fused = R.rrf(dense, kw)
    R.RRF_K = 60
    top = [i for i, _ in fused]
    rec['rrf_tie_at_5'] = len(fused) > 5 and fused[4][1] == fused[5][1]
    rec['top1'] = {'dense': dscore.get(dense[0]) if dense else None, 'kw': kscore.get(kw[0]) if kw else None,
                   'rrf': fused[0][1] if fused else None}
    if cfg['rerank']:
        top = ctx['rr'].order(cfg['rerank'], text, top, index)
    rec['dense_rank'] = {str(j): r + 1 for r, j in enumerate(dense)}
    rec['kw_rank'] = {str(j): r + 1 for r, j in enumerate(kw)}
    return top, set(dense) | set(kw), allowed, rec


# ---------- 지표 ----------
def dcg(rel):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rel))


def metrics(top, cands, allowed, gold, recoverable, index):
    """한 문항의 쪽 단위 지표(k = 1·3·5·10)와 실패 유형. gold는 (PDF, 쪽) 목록. 회수 가능은 이 카드 묶음에 카드가 있는 쪽."""
    G, docs = set(gold), {d for d, _ in gold}
    RG = {p for p in G if index.have[p]}  # [왜] 청킹마다 카드가 있는 쪽이 달라 회수 가능 쪽을 색인 기준으로 센다
    found = [(index.cards[c]['doc'], index.cards[c]['page']) for c in top]
    first_page = next((i + 1 for i, f in enumerate(found) if f in G), None)
    first_doc = next((i + 1 for i, f in enumerate(found) if f[0] in docs), None)
    m = {'page_mrr': 1 / first_page if first_page and first_page <= 10 else 0.0}
    for k in KS:
        hit = {f for f in found[:k] if f in G}
        dedup = list(dict.fromkeys(found[:k]))  # 같은 쪽 카드는 한 번만 센다
        m[f'page_hit@{k}'] = float(bool(hit))
        m[f'page_recall@{k}'] = len(hit) / len(G)
        m[f'page_recall_rec@{k}'] = len(hit & RG) / len(RG) if RG else None
        m[f'all_evidence@{k}'] = float(hit == G)
        m[f'all_evidence_rec@{k}'] = float(RG <= hit) if RG else None
        m[f'page_ndcg@{k}'] = dcg([1 if f in G else 0 for f in dedup]) / dcg([1] * min(k, len(G)))
        legacy = [2 if f in G else 1 if f[0] in docs else 0 for f in found[:k]]
        m[f'legacy_ndcg@{k}'] = dcg(legacy) / dcg([2] * k)
        m[f'doc_hit@{k}'] = float(first_doc is not None and first_doc <= k)
        m[f'doc_mrr@{k}'] = 1 / first_doc if first_doc and first_doc <= k else 0.0
    for n in (50, 100):
        got = {f for f in found[:n] if f in G}
        m[f'cand_recall@{n}'] = len(got) / len(G)
    if not m['page_hit@5']:
        gold_cards = {i for i, c in enumerate(index.cards) if (c['doc'], c['page']) in G}
        m['fail'] = ('corpus_missing' if not gold_cards else 'filter_blocked' if allowed is not None and not gold_cards & allowed
                     else 'outside_candidates' if not gold_cards & cands else 'below_top_k')
    return m


def run_cell(cfg, ctx):
    rows, index = [], ctx['index'][cfg['chunk']]
    for q in ctx['qs']:
        top, cands, allowed, rec = search(cfg, q, ctx)
        rows.append({'id': q['id'], 'pdf': q['pdf'], **metrics(top, cands, allowed, q['gold'], q['rec'], index),
                     'top': [[c, index.cards[c]['sha256'][:12], index.cards[c]['doc'], index.cards[c]['page']] for c in top[:10]],
                     'candidates': sorted(cands), 'search': rec})
    keys = [k for k in rows[0] if '@' in k or k == 'page_mrr']
    summ = {k: (round(sum(r[k] for r in rows if r[k] is not None) / max(1, sum(r[k] is not None for r in rows)), 4)) for k in keys}
    summ['fails'] = dict(Counter(r.get('fail') for r in rows if r.get('fail')))
    summ['ties_at_5'] = sum(any(r['search'].get(t) for t in ('dense_tie_at_5', 'kw_tie_at_5', 'rrf_tie_at_5')) for r in rows)
    summ['empty_results'] = sum(bool(r['search'].get('empty')) for r in rows)
    return {'name': name(cfg), 'cfg': cfg, 'summary': summ, 'rows': rows}


# ---------- 비교 ----------
def sign_p(w, l):
    """양측 정확 부호 검정 p(동률 제외, 이항 0.5)."""
    n = w + l
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(w, l) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(a, b, metric):
    """b − a: 승/패/동률, 평균 차이, 부트스트랩 95% 구간(1만 번, seed 0), 부호 검정 p, 판정, PDF별·PDF 하나 빼기."""
    import numpy as np
    pairs = [(x[metric], y[metric], x['pdf']) for x, y in zip(a['rows'], b['rows']) if x[metric] is not None and y[metric] is not None]
    d = np.array([y - x for x, y, _ in pairs])
    w, l = int((d > 0).sum()), int((d < 0).sum())
    boot = np.random.default_rng(0).choice(d, (10_000, len(d))).mean(1)
    lo, hi = (float(v) for v in np.percentile(boot, [2.5, 97.5]))
    verdict = '개선' if w - l >= 5 and lo > 0 else '악화' if l - w >= 5 and hi < 0 else '차이 입증 못 함'
    by_pdf = defaultdict(list)
    for (x, y, p), dd in zip(pairs, d):
        by_pdf[p].append(dd)
    lopo = [float(np.mean([dd for (_, _, p), dd in zip(pairs, d) if p != pdf])) for pdf in by_pdf if len(by_pdf) > 1]
    return {'W': w, 'L': l, 'T': len(d) - w - l, 'mean_diff': round(float(d.mean()), 4), 'ci95': [round(lo, 4), round(hi, 4)],
            'sign_p': round(sign_p(w, l), 4), 'verdict': verdict,
            'per_pdf_mean_diff': {p: round(float(np.mean(v)), 4) for p, v in by_pdf.items()},
            'leave_one_pdf_out': [round(min(lopo), 4), round(max(lopo), 4)] if lopo else None}


# ---------- 준비 ----------
def v2_questions():
    """채점 19문항의 질의 · 품번 · 정답 쪽. 서비스 search()와 같은 품번 규칙을 쓴다(context와 서비스 경로 측정이 함께 쓴다)."""
    from backend.graph.nodes import find_parts, read_input
    qrels = json.load(open(QRELS, encoding='utf-8'))
    if qrels['meta']['dataset_sha256'] != V2_SHA:
        raise SystemExit('qrels가 다른 평가셋에서 만들어졌다')
    rewrites = json.load(open(REWRITE, encoding='utf-8'))['queries']
    items = {it['id']: it for it in load_v2()}
    qs = []
    for qid, g in qrels['qrels'].items():
        st = read_input({'input': items[qid]['input']})
        part = st.get('target_part') or {}
        refs = {part.get('ref', '')} | {n.split('.')[0] for net in part.get('nets', []) for n in net['nodes']}
        parts = find_parts(st['question'], refs) or find_parts(part.get('value', ''), refs)  # 서비스 search() 규칙
        rec = [tuple(p) for p in g['pages'] if p not in g['unrecoverable']]
        qs.append({'id': qid, 'pdf': g['pdf'], 'gold': [tuple(p) for p in g['pages']], 'rec': rec, 'parts': parts,
                   'text': {'Q2': st['question'], 'Q3': rewrites[qid]['Q3']}})
    return qs


def context(args, chunks=('C',)):
    qs = v2_questions()
    index = {'C': Index(args.cards, 'C')}
    for ch in chunks:
        if ch != 'C':
            index[ch] = Index(Path(args.chunk_dir) / f'{ch}.jsonl', ch)
    return {'qs': qs, 'index': index, 'vec': Vectors(args), 'rr': Reranker(args.rerank_cache)}


def official_cells(extra_rerankers=()):
    """사전 등록 #24의 공식 칸: 기준 하나에서 한 조건만 바꾸고(E1~E8), 칸마다 필터 끔도 잰다.
    extra_rerankers: GPU에서 돌릴 로컬 CrossEncoder 이름(예: BAAI/bge-reranker-v2-m3). 비어 있으면 Voyage 2종만."""
    cells = []

    def add(exp, base_cfg, **change):
        for F in ('part', None):
            cells.append((exp, dict(base_cfg, F=F), dict(base_cfg, F=F, **change)))

    for S, kw in (('dense', 'bm25'), ('bm25', 'bm25'), ('bm25', 'tfidf'), ('hybrid', 'tfidf')):
        add('E1', BASE, S=S, kw=kw)
    for rr in ('rerank-3', 'rerank-3-lite', *extra_rerankers):
        add('E2', BASE, rerank=rr)
    for F in (None, 'category', 'kind', 'part+kind'):
        cells.append(('E3', BASE, dict(BASE, F=F)))
    add('E4', BASE, Q='Q3')
    for m in ('te3l', 'te3l1536', 'v4lite', 'v4', 'v4large', 'kure', 'qwen06', 'bgem3', 'qwen4b', 'qwen8b'):
        add('E5', BASE, model=m)
    f1000 = dict(BASE, chunk='fixed1000_100')
    add('E6', BASE, chunk='fixed1000_100')
    for ch in ('fixed500_100', 'fixed2000_100', 'fixed1000_0', 'fixed1000_400', 'semantic'):
        add('E6', f1000, chunk=ch)
    add('E6', BASE, chunk='semantic')
    bge = dict(BASE, chunk='fixed1000_100', model='bgem3')
    add('E6L', bge, model='bgem3late')  # #24 덧붙임: 같은 모델(bge-m3) 같은 청크의 일반 임베딩 대비 late chunking
    for T in ('T1', 'T2', 'T3'):
        add('E7', BASE, T=T)
    for change in ({'rrf_k': 10}, {'rrf_k': 100}, {'n': 100}):
        add('E8', BASE, **change)
    return cells


PRIMARY = ('page_hit@5', 'page_recall@5', 'page_recall_rec@5', 'all_evidence@5', 'page_mrr', 'page_ndcg@5')


def official(args):
    cells = official_cells(tuple(x for x in (args.extra_rerankers or '').split(',') if x))
    if args.exps:
        cells = [c for c in cells if c[0] in args.exps.split(',')]
    chunks = sorted({c for _, a, b in cells for c in (a['chunk'], b['chunk'])})
    avail = [c for c in chunks if c == 'C' or (Path(args.chunk_dir) / f'{c}.jsonl').exists()]
    ctx = context(args, avail)
    done, comps, skipped = {}, [], []
    for exp, a, b in cells:
        try:
            for cfg in (a, b):
                if name(cfg) not in done:
                    if cfg['chunk'] not in ctx['index']:
                        raise FileNotFoundError(f"청킹 {cfg['chunk']} 벡터 없음")
                    done[name(cfg)] = run_cell(cfg, ctx)
            comps.append({'exp': exp, 'base': name(a), 'cell': name(b),
                          **{m: compare(done[name(a)], done[name(b)], m) for m in PRIMARY}})
        except Exception as e:  # noqa: BLE001  [왜] 사전 등록: 한 칸이 막혀도 나머지를 재고 이유를 남긴다
            skipped.append({'exp': exp, 'cell': name(b), 'reason': f'{type(e).__name__}: {str(e)[:160]}'})
    out = {'meta': run_meta(args, ctx), 'cells': list(done.values()), 'comparisons': comps, 'skipped': skipped}
    jdump(out, args.out)
    base = done[name(BASE)]['summary']
    print('기준', {k: base[k] for k in PRIMARY + ('doc_hit@5', 'cand_recall@50')})
    for exp in sorted({c['exp'] for c in comps}):  # 화면에는 실험마다 판정 개수만(전체는 json)
        cs = [c for c in comps if c['exp'] == exp]
        print(exp, len(cs), '비교 |', {m: dict(Counter(c[m]['verdict'] for c in cs)) for m in PRIMARY[:2]})
    print('건너뜀', len(skipped), [s['cell'] for s in skipped][:6], '| 새 리랭크', ctx['rr'].new_calls, ctx['rr'].new_tokens)


def run_meta(args, ctx):
    return {'preregister': '#24', 'run_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'dataset_sha256': V2_SHA,
            'qrels_sha256': hashlib.sha256(QRELS.read_bytes()).hexdigest(),
            'rewrite_sha256': hashlib.sha256(REWRITE.read_bytes()).hexdigest(),
            'cards_sha256': hashlib.sha256(Path(args.cards).read_bytes()).hexdigest(),
            'max_card_chars': max(len(c['text']) for c in ctx['index']['C'].cards), 'k': KS,
            'commit': os.popen('git -C "%s" rev-parse --short HEAD' % ROOT).read().strip()}


def noresult(args):
    """관련 19 · 비관련 35문항(v2, candidate_find 제외)의 1위 점수 분포와 가장 잘 가르는 임계값(1주 16강)."""
    from backend.graph.nodes import find_parts, read_input
    ctx = context(args)
    items = [it for it in load_v2() if it.get('question_type') != 'candidate_find']
    rel_ids = {q['id'] for q in ctx['qs']}
    qs = []
    for it in items:
        if it['id'] in rel_ids or it['kind'] == 'irrelevant':
            st = read_input({'input': it['input']})
            part = st.get('target_part') or {}
            refs = {part.get('ref', '')} | {n.split('.')[0] for net in part.get('nets', []) for n in net['nodes']}
            qs.append({'id': it['id'], 'rel': it['id'] in rel_ids, 'parts': find_parts(st['question'], refs) or find_parts(part.get('value', ''), refs),
                       'text': {'Q2': st['question']}})
    out = {}
    for F in ('part', None):
        for S, key in (('dense', 'dense'), ('bm25', 'kw'), ('hybrid', 'rrf')):
            cfg = dict(BASE, S=S, F=F)
            vals = []
            for q in qs:
                _, _, _, rec = search(cfg, q, ctx)
                vals.append((q['rel'], None if rec.get('empty') else rec['top1'][key]))
            out[f'{S}|{F}'] = threshold(vals)
    jdump({'meta': {'preregister': '#24', 'relevant': sum(q['rel'] for q in qs), 'irrelevant': sum(not q['rel'] for q in qs)},
           'methods': out}, args.out)
    for k, v in out.items():
        print(k, {x: v[x] for x in ('best_threshold', 'balanced_accuracy', 'empty_relevant', 'empty_irrelevant')})


def threshold(vals):
    """1위 점수가 임계값 이상이면 답, 아니면 no_result. 빈 결과는 no_result. 균형 정확도가 가장 높은 임계값."""
    rel = [v for r, v in vals if r and v is not None]
    irr = [v for r, v in vals if not r and v is not None]
    n_rel, n_irr = sum(r for r, _ in vals), sum(not r for r, _ in vals)
    best = (0, None)
    for t in sorted(set(rel + irr)):
        tp = sum(v >= t for v in rel) / n_rel
        tn = (n_irr - sum(v >= t for v in irr)) / n_irr
        best = max(best, ((tp + tn) / 2, t))
    q = lambda xs: [round(min(xs), 4), round(sorted(xs)[len(xs) // 2], 4), round(max(xs), 4)] if xs else None  # noqa: E731
    return {'relevant_min_med_max': q(rel), 'irrelevant_min_med_max': q(irr), 'best_threshold': best[1],
            'balanced_accuracy': round(best[0], 4), 'empty_relevant': n_rel - len(rel), 'empty_irrelevant': n_irr - len(irr)}


# ---------- E6 청킹 ----------
VARIANTS = {'fixed1000_100': (1000, 100), 'fixed500_100': (500, 100), 'fixed2000_100': (2000, 100),
            'fixed1000_0': (1000, 0), 'fixed1000_400': (1000, 400)}


def make_chunks(args):
    """쪽마다 Docling 마크다운을 고정 길이 · 겹침으로 자른다(11-01 청킹 A와 같은 자르기를 쪽 안에서). 의미 단위는 embed 단계에서."""
    from docling_core.types.doc import DoclingDocument
    meta = {}
    for c in map(json.loads, open(args.cards, encoding='utf-8')):
        meta.setdefault(c['doc'], {'category': c['category'], 'parts': c.get('parts') or []})
    files = sorted(Path(args.docling_dir).glob('*.json'))
    Path(args.chunk_dir).mkdir(parents=True, exist_ok=True)
    outs = {v: open(Path(args.chunk_dir) / f'{v}.jsonl', 'w', encoding='utf-8') for v in VARIANTS}
    sent = open(Path(args.chunk_dir) / 'semantic_sentences.jsonl', 'w', encoding='utf-8')
    for f in files:
        doc_name = f.name[:-5]
        doc = DoclingDocument.load_from_json(f)
        for p in sorted(doc.pages):
            text = doc.export_to_markdown(page_no=p).strip()
            if not text:
                continue
            base = {'doc': doc_name, 'page': p, 'category': meta.get(doc_name, {}).get('category', ''),
                    'parts': meta.get(doc_name, {}).get('parts', []), 'kind': 'fixed', 'table': None}
            for v, (size, ov) in VARIANTS.items():
                for i in range(0, max(len(text) - ov, 1), size - ov):
                    t = text[i:i + size]
                    outs[v].write(json.dumps({**base, 'text': t, 'sha256': sha(t)}, ensure_ascii=False) + '\n')
            parts = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]
            sent.write(json.dumps({**base, 'sentences': parts}, ensure_ascii=False) + '\n')
    for fh in list(outs.values()) + [sent]:
        fh.close()
    print('청킹', {v: sum(1 for _ in open(Path(args.chunk_dir) / f'{v}.jsonl')) for v in VARIANTS})


def embed_variant(args, variant):
    """변형 카드의 서로 다른 본문을 3-small로 임베딩해 <변형>.f32·.sha.txt에 이어 쓴다. semantic이면 먼저 문장을 임베딩해 자른다."""
    import numpy as np
    from backend.services.llm import embed_texts
    d = Path(args.chunk_dir)
    if variant == 'semantic' and not (d / 'semantic.jsonl').exists():
        semantic_chunks(args, embed_texts)
    texts = {}
    for c in map(json.loads, open(d / f'{variant}.jsonl', encoding='utf-8')):
        texts[c['sha256']] = c['text']
    fs = d / f'{variant}.sha.txt'
    done = set(open(fs).read().split()) if fs.exists() else set()
    todo = sorted((s for s in texts if s not in done), key=lambda s: len(texts[s]))
    tokens = 0
    for i in range(0, len(todo), 128):
        part = todo[i:i + 128]
        vecs, n, _, model_id = embed_texts([texts[s] for s in part])
        assert model_id.endswith('text-embedding-3-small'), model_id
        with open(d / f'{variant}.f32', 'ab') as f:
            f.write(np.asarray(vecs, np.float32).tobytes())
        with open(fs, 'a') as f:
            f.write(''.join(s + '\n' for s in part))
        tokens += n
    print(variant, '본문', len(texts), '새 토큰', tokens)


def semantic_chunks(args, embed_texts):
    """의미 단위 청킹: 쪽 안의 이웃 문장 임베딩 거리가 그 문서의 95백분위를 넘는 곳에서 자른다(LangChain SemanticChunker 기본값).
    한 덩어리가 2,000자를 넘으면 더 자른다."""
    import numpy as np
    d = Path(args.chunk_dir)
    pages = [json.loads(l) for l in open(d / 'semantic_sentences.jsonl', encoding='utf-8')]
    uniq = list(dict.fromkeys(s for p in pages for s in p['sentences']))
    vec = {}
    for i in range(0, len(uniq), 256):
        part = uniq[i:i + 256]
        vecs, _, _, _ = embed_texts(part)
        vec.update({s: np.asarray(v, np.float32) for s, v in zip(part, vecs)})
    by_doc = defaultdict(list)
    for p in pages:
        by_doc[p['doc']].append(p)
    with open(d / 'semantic.jsonl', 'w', encoding='utf-8') as out:
        for doc, ps in by_doc.items():
            dist = [1 - float(vec[a] @ vec[b]) for p in ps for a, b in zip(p['sentences'], p['sentences'][1:])]
            cut = float(np.percentile(dist, 95)) if dist else 1.0
            for p in ps:
                chunk = [p['sentences'][0]]
                for a, b in zip(p['sentences'], p['sentences'][1:]):
                    if 1 - float(vec[a] @ vec[b]) > cut or len(' '.join(chunk + [b])) > 2000:
                        t = '\n'.join(chunk)
                        out.write(json.dumps({**{k: p[k] for k in ('doc', 'page', 'category', 'parts', 'kind', 'table')},
                                              'text': t, 'sha256': sha(t)}, ensure_ascii=False) + '\n')
                        chunk = []
                    chunk.append(b)
                t = '\n'.join(chunk)
                out.write(json.dumps({**{k: p[k] for k in ('doc', 'page', 'category', 'parts', 'kind', 'table')},
                                      'text': t, 'sha256': sha(t)}, ensure_ascii=False) + '\n')


BGE_REV = '5617a9f61b028005a4858fdac845db406aefb181'  # 11-03 HF 작업과 같은 bge-m3 revision


def gpu_embed(args, variant):
    """GPU: 고정 길이 변형 카드를 bge-m3로 임베딩한다. --mode bgem3는 일반(카드를 따로 읽고 모델 기본 CLS 풀링),
    bgem3late는 late chunking(쪽 전체를 한 번 읽어 카드 구간의 토큰 임베딩을 평균). 사전 등록 #24 덧붙임."""
    import numpy as np
    import torch
    d = Path(args.chunk_dir)
    cards = [json.loads(l) for l in open(d / f'{variant}.jsonl', encoding='utf-8')]
    size, ov = VARIANTS[variant]
    t0, fallback = time.time(), 0
    if args.mode == 'bgem3':
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer('BAAI/bge-m3', revision=BGE_REV, device='cuda', model_kwargs={'torch_dtype': torch.bfloat16})
        m.max_seq_length = 1024
        text = {c['sha256']: c['text'] for c in cards}
        keys = list(text)
        order = sorted(range(len(keys)), key=lambda i: len(text[keys[i]]))  # 길이순으로 묶어 패딩을 줄인다
        V = m.encode([text[keys[i]] for i in order], batch_size=64, normalize_embeddings=True, convert_to_numpy=True,
                     show_progress_bar=False)
        out = np.empty_like(V)
        out[order] = V
    else:
        from transformers import AutoModel, AutoTokenizer
        tok = AutoTokenizer.from_pretrained('BAAI/bge-m3', revision=BGE_REV)
        lm = AutoModel.from_pretrained('BAAI/bge-m3', revision=BGE_REV, torch_dtype=torch.bfloat16).cuda().eval()
        out, keys = np.zeros((len(cards), 1024), np.float32), [f'card:{k}' for k in range(len(cards))]
        pages = defaultdict(list)
        for k, c in enumerate(cards):
            pages[c['doc'], c['page']].append(k)
        for ks in pages.values():
            page = cards[ks[0]]['text'] + ''.join(cards[k]['text'][ov:] for k in ks[1:])  # 겹친 청크를 이어 쪽 원문을 되살린다
            enc = tok(page, return_offsets_mapping=True, truncation=True, max_length=8192, return_tensors='pt')
            offs = enc.pop('offset_mapping')[0].tolist()
            with torch.no_grad():
                H = lm(**enc.to('cuda')).last_hidden_state[0].float().cpu().numpy()
            for j, k in enumerate(ks):
                a, b = j * (size - ov), j * (size - ov) + len(cards[k]['text'])
                idx = [t for t, (x, y) in enumerate(offs) if y > x and x < b and y > a]
                if idx:
                    v = H[idx].mean(0)
                else:  # [주의] 8192토큰 밖이라 구간 토큰이 없으면 그 카드만 따로 읽은 CLS로 대신하고 수를 센다
                    fallback += 1
                    with torch.no_grad():
                        v = lm(**tok(cards[k]['text'], truncation=True, max_length=1024, return_tensors='pt').to('cuda')
                               ).last_hidden_state[0, 0].float().cpu().numpy()
                out[k] = v / np.linalg.norm(v)
    np.asarray(out, np.float32).tofile(d / f'{variant}.{args.mode}.f32')
    (d / f'{variant}.{args.mode}.sha.txt').write_text(''.join(k + '\n' for k in keys))
    log = {'model': 'BAAI/bge-m3', 'revision': BGE_REV, 'mode': args.mode, 'variant': variant, 'rows': len(keys),
           'cards': len(cards), 'fallback_cls': fallback, 'dtype': 'bfloat16', 'gpu': torch.cuda.get_device_name(0),
           'sec': round(time.time() - t0, 1)}
    jdump(log, d / f'{variant}.{args.mode}.log.json')
    print(json.dumps(log, ensure_ascii=False))


# ---------- 탐색 격자 ----------
def explore(args):
    """공식 측정 뒤의 탐색(사전 등록 #24 '탐색'): 임베딩 11 × 리랭커 3 × 질의 2 × 방식 × 필터 2. 판정에 쓰지 않는다."""
    ctx = context(args)
    models = ['te3s', 'te3l', 'te3l1536', 'v4lite', 'v4', 'v4large', 'kure', 'qwen06', 'bgem3', 'qwen4b', 'qwen8b']
    cells, skipped = [], []
    for rr in (None, 'rerank-3', 'rerank-3-lite'):
        for Q in ('Q2', 'Q3'):
            for F in ('part', None):
                cfgs = [dict(BASE, S='bm25', Q=Q, F=F, rerank=rr)] + [dict(BASE, model=m, S=S, Q=Q, F=F, rerank=rr)
                                                                       for m in models for S in ('dense', 'hybrid')]
                for cfg in cfgs:
                    try:
                        c = run_cell(cfg, ctx)
                        cells.append({'name': c['name'], 'cfg': cfg, 'summary': c['summary']})
                    except Exception as e:  # noqa: BLE001
                        skipped.append({'cell': name(cfg), 'reason': f'{type(e).__name__}: {str(e)[:120]}'})
    jdump({'meta': {**run_meta(args, ctx), 'label': '탐색(판정에 쓰지 않음)'}, 'cells': cells, 'skipped': skipped}, args.out)
    top = sorted(cells, key=lambda c: (c['summary']['page_hit@5'], c['summary']['page_recall@5']), reverse=True)[:8]
    for c in top:
        print(c['name'], c['summary']['page_hit@5'], c['summary']['page_recall@5'])
    print('칸', len(cells), '건너뜀', len(skipped), '| 새 리랭크', ctx['rr'].new_calls, ctx['rr'].new_tokens)


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('cmd', choices=['qrels', 'official', 'noresult', 'chunks', 'embed', 'gpu_embed', 'explore'])
    p.add_argument('variant', nargs='?')
    p.add_argument('--cards', default=str(OUTSIDE / 'corpus/tsc/chunks/chunks.jsonl'))
    p.add_argument('--vectors', default=str(OUTSIDE / '전자_데이터시트/evidence/full_grid/vectors'))
    p.add_argument('--qvec-dir', default=str(OUTSIDE / '전자_데이터시트/evidence/full_grid/inputs'))
    p.add_argument('--chunk-dir', default=str(OUTSIDE / 'corpus/tsc/chunks/variants'))
    p.add_argument('--docling-dir', default=str(OUTSIDE / 'corpus/tsc/parsed/docling'))
    p.add_argument('--rerank-cache', default=str(OUTSIDE / '전자_데이터시트/evidence/full_grid/out/rerank_cache.jsonl'))
    p.add_argument('--out', default=None)
    p.add_argument('--extra-rerankers', default='', help='E2에 더할 로컬 리랭커(쉼표). GPU 단계에서만')
    p.add_argument('--exps', default='', help='이 실험만(쉼표, 예: E2,E6L)')
    p.add_argument('--mode', default='bgem3', choices=['bgem3', 'bgem3late'], help='gpu_embed: 일반 또는 late chunking')
    a = p.parse_args()
    os.environ.setdefault('DEMO_MODE', '0')  # [주의] 기본값 1이면 서비스 retrieve가 dense를 끈다. 이 실행기는 retrieve()를 부르지 않지만 llm 설정을 맞춘다
    sys.path.insert(0, str(ROOT))
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    if a.cmd == 'qrels':
        make_qrels(a.cards)
    elif a.cmd == 'chunks':
        make_chunks(a)
    elif a.cmd == 'embed':
        embed_variant(a, a.variant)
    elif a.cmd == 'gpu_embed':
        gpu_embed(a, a.variant)
    else:
        a.out = a.out or str(ROOT / f'evals/results/retrieval/d3_{a.cmd}_{time.strftime("%Y-%m-%d")}.json')
        globals()[a.cmd](a)


if __name__ == '__main__':
    main()
