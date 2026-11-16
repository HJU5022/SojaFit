# 유료 실행 비용 기록 (d12, 2026-11-17)

예산 상한 $8(OpenRouter + Voyage + Exa 합). 실행 전에 저장소 기록의 문항당 비용으로 어림하고, 실행 뒤 실제 값을 적는다. OpenRouter 키 사용액은 다른 작업과 같은 키라 차이는 상한으로만 쓴다.

| # | 실행 | 실행 전 어림 | 어림 근거 | 실행 뒤 |
|---|---|---|---|---|
| 1 | 동결 v3 50문항 1세트, 운영 설정(`DEMO_MODE=0 EVAL_WEB=1 WEB_PREFETCH=1`) | LLM $0.03 ~ 0.05 + Voyage < $0.01 + Exa 최대 약 $0.75(50문항 × 최대 3회 × $0.005) = 최대 약 $0.8 | README 5절 "웹을 켠 11-14 측정 0.032 ~ 0.044달러(`cost_usd` 합)" | 실행기 `cost_usd` 합 **$0.0361**(LLM). OpenRouter 키 사용액 27.3250 → 27.3630(차 $0.0380, 같은 키의 다른 작업 포함 가능). Voyage 50건(질문 임베딩 · 리랭크, 요금 미측정, < $0.01 어림). 웹 단계 24회(`grade2_datasheet` 12 · `grade3_reference` 12), Exa 요금 미측정(어림 ≤ $0.25) |
| 2 | 검색만 재측정 `run_retrieval_service`(R1 84 + v2 19 = 103문항, 서비스 `retrieve()`, 질의 재작성 20회) | Voyage 임베딩 103건 + rerank-3 103회 ≈ $0.1, OpenRouter 재작성 20회 ≈ $0.01 → 약 $0.15 | 11-04 같은 실행기 `openrouter_spent_usd` 0.0 · 0.0012, 11-16 후보 수 실험 Voyage 약 $0.06(`docs/worklog/jeongun.md` 11-16) | 실행기 `openrouter_spent_usd` **$0.0005**(재작성 20회). Voyage 임베딩 103건 + rerank-3 103회 요금 미측정(어림 ≤ $0.1) |
