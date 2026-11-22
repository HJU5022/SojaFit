# 0014 Supervisor는 Sonnet, 서브에이전트는 Haiku, 채점은 Luna로 노드별 모델을 나눈다

- 날짜: 2026-11-05
- 상태: 채택, 일부 대체됨 → [0017](0017-supervisor를-haiku로-바꾸고-찾기-질문은-코드가-판정-에이전트로-맞춘다.md)
- 현재: Supervisor도 `anthropic/claude-haiku-5.5`이고, 종합 `synth`만 `anthropic/claude-sonnet-5.5`, 채점 `grade`는 `openai/gpt-6-luna`다(`backend/services/langfuse_prompts.py`의 `NODE_MODELS`).
- 근거: 조장 결정(11-05), 사전 등록 #33(Supervisor 후보 6종 3회 비교, 오세창), #37 · #38 측정
- 일부 바뀜(11-10): "Supervisor는 Sonnet"은 Haiku로 바뀌었다(종합 `synth`는 Sonnet 그대로) → [ADR 0017](0017-supervisor를-haiku로-바꾸고-찾기-질문은-코드가-판정-에이전트로-맞춘다.md).
- 바꾸는 것: [ADR 0010](0010-그래프-llm은-haiku로-시작한다.md)의 "LLM 노드는 Haiku 하나로 시작"을 노드별 모델로 바꾼다. 0010의 "채점기는 생성과 다른 회사 모델" 원칙은 그대로 둔다.

## 결정
- 노드별 모델은 `backend/services/langfuse_prompts.py`의 `NODE_MODELS` 한 곳에서 정한다(커밋 `f385ff7`).
  - Supervisor: `anthropic/claude-sonnet-5.5`
  - 그 밖의 LLM 노드(`route` · `rewrite` · `generate`, 검색 · 작성 에이전트가 감싸는 노드): `anthropic/claude-haiku-5.5`
  - 채점(`grade`): `openai/gpt-6-luna`
- 채점 모델은 길을 정하는 모델(Supervisor)과도 다른 회사 모델로 둔다.

## 이유
- Haiku는 Supervisor 일(질문 종류를 정하고 다음 단계를 고르는 일)에서 약했다. #33에서 같은 동결 v2 70문항을 3번 재니, Haiku는 형식에 맞는 결정 46~50/70, 관련 35문항의 질문 종류 정답 21~23/35였다. 같은 조건에서 Luna는 65~66/70 · 33~35/35, Jev는 70/70 · 33/35였다(`evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json`).
- Luna는 #33에서 충분히 잘했지만 두 가지 때문에 Supervisor로 쓰지 않았다.
  - 채점 모델이 Luna다. Supervisor도 Luna면 길을 정한 모델과 채점하는 모델이 같아진다. 그래서 다른 회사(Anthropic) 모델에서 고른다.
  - 여러 단계를 이어 판단하는 Supervisor 자리에 맞는 모델인지는 조장이 의문으로 봤다(측정한 것은 아니다).
- Anthropic 모델 중에서는 Haiku 한 단계 위인 Sonnet을 골랐다.
- 서브에이전트 노드는 맡은 일이 좁아(검색어 재작성 · 답 작성) Haiku를 유지한다. 0010의 10문항 비교에서 답 작성은 Haiku와 Sonnet이 같았다.

## 결과
- #38(Sonnet Supervisor로 멀티 에이전트 첫 측정): 70문항 중 67 끝남. 끝난 관련 32문항의 질문 종류 일치 32/32다. 실패 3건은 Supervisor 지시(`brief`)가 300자 제한을 넘은 것이라 800자로 늘렸다(커밋 `7d4383f`).
- 비용이 크다. #38 한 번에 Sonnet 1.77달러, 전체 약 1.82달러로 단일 그래프 #37(0.0426달러)의 약 43배다. Sonnet을 쓰는 측정은 사전 등록에 예산을 먼저 적는다.
- Sonnet과 Luna를 Supervisor 자리에서 같은 조건으로 비교하지 않았다. #33(질문 분류만 따로 잼)과 #38(그래프 전체)은 재는 방식이 달라 숫자를 바로 비교할 수 없다.
- #38은 팀 레포 복제본(lab)에서 Supervisor만 Anthropic API를 직접 불러 쟀다(사전 등록 #38 "실행 전 변경"). 팀 레포 기본 경로는 OpenRouter다.
