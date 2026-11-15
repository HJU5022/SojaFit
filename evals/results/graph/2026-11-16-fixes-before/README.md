# 동결 전 백엔드 수정 묶음, 기준 팔 `before` (2026-11-15 측정)

사전 등록: [evals/guides/preregister.md](../../../guides/preregister.md) 「2026-11-15 jeongun · 동결 전 백엔드 수정 묶음(web-to-main) 정확도 회귀 확인」(커밋 `af8f7e38`). 비교 결과는 [2026-11-16-fixes-after/README.md](../2026-11-16-fixes-after/README.md).

- 코드: 커밋 `af8f7e38`(코드는 그룹 1 끝 `f732afba`와 같음). 다른 팀 실험(`sojafit-exp-*` 컨테이너)과 겹치지 않으려고 그 커밋을 `git archive`로 임시 폴더에 풀어 돌렸다. 그래서 `set1.json`의 `git: 50c4c92`는 그 임시 폴더의 해시이고 저장소 커밋이 아니다.
- 명령(저장소 루트 아님, 위 임시 폴더에서): `EVAL_WEB=0 WEB_PREFETCH=0 EXA_WEB_SEARCH_ENABLED=0 EXA_API_KEY= DEMO_MODE=0 GATE_WARMUP=1 FIND_N_DOCS=5 RAGAS_ENABLED=0 uv run --env-file <.env> python -m evals.runners.run_gate evals/dataset_v3.jsonl --out <이 폴더> --sets 1 --keep-going --p95 120`
- 결과: 50/50 통과, p50 4.3초, p95 9.1초, LLM 비용 0.0297달러(LLM 80번), 판정 일치 10/10(v3-01~10), 실패 · 오류 0, Exa 흔적 0. 한 번 돌린 값이라 회차 간 흔들림(같은 코드 p95가 3.8초 흔들린 기록이 있음)을 감안한다.
