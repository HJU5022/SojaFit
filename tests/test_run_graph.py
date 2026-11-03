"""그래프 평가 실행: 최종 메모장에서 Langfuse에 붙일 실행 점수를 바르게 뽑는지 확인한다.

- 역할: evals/run_graph.py의 run_scores가 경로·검색 횟수·카드 수·인용 검사 점수를 뽑고, 거절로 끝나면 인용 검사 점수를 빼는지 확인한다.
- 하지 않는 일: Langfuse·LLM 없이 돈다. 답이 맞았는지는 보지 않는다.
- 출처: SPEC 7절(그래프 평가 실행), docs/GATES.md G6
"""
from evals.run_graph import run_scores


def test_answer_path_scores_include_citation_check():
    state = {"path": ["입력 읽기", "라우팅", "검색", "채점", "생성"], "question_type": "rating", "tries": 1,
             "docs": [{"chunk_id": 7}, {"chunk_id": 8}], "passed": [7], "answer": "VRRM은 20 V다 [7]. 근거 없는 문장.",
             "check": {"fake_citations": ["999"], "uncited_sentences": 1, "used": ["7"]}}
    scores = run_scores(state, 2.34, ["Route", "Grade", "Answer"])
    assert scores["path"][:2] == ("입력 읽기>라우팅>검색>채점>생성", "CATEGORICAL")
    assert scores["not_found"][0] == 0.0 and scores["tries"][0] == 1.0 and scores["llm_calls"][0] == 3.0
    assert scores["docs_found"][0] == 2.0 and scores["passed_cards"][0] == 1.0 and scores["latency_s"][0] == 2.3
    assert scores["fake_citations"][0] == 1.0 and scores["uncited_sentences"][0] == 1.0


def test_refuse_path_has_no_citation_scores():
    state = {"path": ["입력 읽기", "라우팅", "검색", "채점", "거절"], "question_type": "rating", "tries": 1, "docs": [],
             "passed": [], "answer": "문서로 확인 안 됨: 1N4001 데이터시트를 찾지 못했습니다.", "check": {}}
    scores = run_scores(state, 0.8, ["Route"])
    assert scores["not_found"][0] == 1.0
    assert "fake_citations" not in scores and "uncited_sentences" not in scores
