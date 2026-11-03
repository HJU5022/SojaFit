"""평가셋의 관련 문항으로 검색 지표(문서 Recall@k, MRR, Page Hit@k)를 잰다. 검색 담당이 손으로 돌린다.

- 역할: 데이터시트 근거가 있는 관련 문항마다 backend.rag.retrieve.retrieve(question, k, method)를 부르고,
  정답 문서(gold_chunks의 PDF 이름)가 몇 위에 나왔는지, 정답 페이지까지 맞혔는지 센다. 결과를 json으로 남긴다.
  method는 hybrid(기본)·dense·bm25 중 하나이고 summary에 같이 적는다.
- 하지 않는 일: 답변 채점, 비관련 문항의 거절 판정. 회로 근거만 있는 관련 문항과 후보 찾기 문항(question_type
  candidate_find, 열린 정답이라 gold_chunks가 예시 후보)은 세지 않고 id만 적는다.
- 출처: docs/specs/rag-pipeline.md What 7·AC-07, evals/guides/dataset-guide.md(gold_chunks 뜻), evals/guides/preregister.md #4(하이브리드)·#16(격자 본평가)
- 원시 결과: 두 번째 인자로 준 json 경로(관례: evals/results/retrieval/retrieval_<방식>_<날짜>.json). summary와 문항별 rows가 들어간다.
- 필요한 것: DATABASE_URL(적재한 코퍼스), 임베딩 키(.env, method가 bm25면 쓰지 않음)
- [주의] 질의 글: 문항에 question 키가 있으면 그것을, 없으면 input 전체를 쓴다. dataset_v1.jsonl에는
  question이 없어 v1 베이스라인은 회로명·넷리스트 경로·조건이 붙은 input 전체로 검색한다. 11-01 실험
  (preregister.md #4~#8, evals/drafts/sets/draft_50.jsonl)은 question만 썼으므로 두 점수는 바로 비교할 수 없다.
  질의 필드를 바꾸려면 먼저 evals/guides/preregister.md에 등록한다.

실행(저장소 루트에서): uv run python -m evals.runners.run_retrieval <평가셋 jsonl> <결과 json> [k] [method]
  예) uv run python -m evals.runners.run_retrieval evals/dataset_v1.jsonl evals/results/retrieval/retrieval.json 5 bm25
"""
import json
import re
import sys
import time


def gold_locations(gold_chunks):
    """gold_chunks("<이름>.pdf, <N>쪽 ..." 꼴)에서 (PDF 이름, 쪽) 목록을 뽑는다."""
    out = []
    for g in gold_chunks:
        # 넷리스트 같은 회로 근거는 "...pdf, N쪽" 꼴이 아니라서 여기서 걸러진다(None)
        m = re.match(r'(.+?\.pdf),\s*(\d+)쪽', g)
        if m:
            out.append((m.group(1), int(m.group(2))))
    return out


def main(dataset_path, out_path, k=5, method='hybrid'):
    """관련 문항마다 검색해 문서 Recall@k·MRR·Page Hit@k·지연 p50을 구하고 json으로 저장한다(k는 문항당 결과 수, method는 hybrid·dense·bm25)."""
    from backend.rag.retrieve import retrieve, warmup
    items = [json.loads(line) for line in open(dataset_path, encoding='utf-8') if line.strip()]
    targets, skipped, open_skipped = [], [], []
    for it in items:
        if it.get('question_type') == 'candidate_find':
            # [왜] 열린 정답(조건을 모두 만족하면 어느 품번이든 정답)이라 gold_chunks의 문서는 예시다. 검색 순위로 채점하면 점수가 틀린다
            open_skipped.append(it['id'])
            continue
        gold = gold_locations(it['gold_chunks']) if it['kind'] == 'relevant' else []
        if gold:
            targets.append((it, gold))
        elif it['kind'] == 'relevant':
            skipped.append(it['id'])  # 회로 근거만 있는 문항
    if not targets:  # [주의] DB에 붙기 전에, 0으로 나누기 전에 무엇이 비었는지 알려 준다
        raise SystemExit(f'평가할 문항이 없습니다: {dataset_path}에 데이터시트 근거가 있는 관련 문항이 0건입니다')
    warmup()  # [왜] 첫 검색의 모델·연결 준비 시간이 지연(sec) 측정에 섞이지 않게 먼저 데운다
    rows = []
    for it, gold in targets:
        t0 = time.perf_counter()
        found = retrieve(it.get('question') or it['input'], k=k, method=method)
        sec = time.perf_counter() - t0
        docs = {d for d, _ in gold}  # 정답 문서(PDF) 집합. 문항 하나에 정답 문서가 여럿일 수 있다
        # rank: 정답 문서가 처음 나온 순위(1부터). 상위 k개에 없으면 None
        rank = next((i + 1 for i, r in enumerate(found) if r['file'] in docs), None)
        # Page Hit: 정답 (문서, 쪽) 쌍이 상위 k개 안에 하나라도 있는가(문서만 맞은 경우는 제외)
        page_hit = any((r['file'], r['page']) in set(gold) for r in found)
        rows.append({'id': it['id'], 'rank': rank, 'page_hit': page_hit, 'sec': round(sec, 3), 'gold': gold,
                     'top': [{'file': r['file'], 'page': r['page'], 'score': round(r['score'], 5),
                              'dense_rank': r['dense_rank'], 'bm25_rank': r['bm25_rank'],
                              'content': r['content'][:120]} for r in found]})
    n = len(rows)
    # doc_recall@k = 정답 문서가 상위 k에 든 문항 비율. doc_mrr = 정답 문서 첫 순위의 역수(1/rank)의 평균, 못 찾은 문항은 0점
    summary = {'dataset': dataset_path, 'method': method, 'k': k, 'questions': n, 'circuit_only_skipped': skipped,
               'candidate_find_skipped': open_skipped,
               f'doc_recall@{k}': round(sum(r['rank'] is not None for r in rows) / n, 3),
               'doc_mrr': round(sum(1 / r['rank'] for r in rows if r['rank']) / n, 3),
               f'page_hit@{k}': round(sum(r['page_hit'] for r in rows) / n, 3),
               'sec_p50': sorted(r['sec'] for r in rows)[n // 2]}  # 지연 중앙값(정렬한 가운데 값)
    # [주의] out_path에 이미 파일이 있으면 덮어쓴다. 이전 원시 결과를 지키려면 날짜를 바꿔 준다
    json.dump({'summary': summary, 'rows': rows}, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4, 5):
        sys.exit(__doc__)
    # [주의] method를 고르려면 k도 앞에 적어야 한다(둘 다 위치 인자)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) >= 4 else 5, *sys.argv[4:])
