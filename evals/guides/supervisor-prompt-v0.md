# Supervisor Prompt V0 평가 절차

이 문서는 확정본이 아닌 Supervisor Prompt V0를 세 후보 모델에서 같은 의미 계약으로 비교하는 오프라인 준비·실행 순서입니다. V0는 라우팅 결정을 평가하기 위한 프로토타입이며 서비스 `build_graph()`에는 아직 연결하지 않았습니다.

## 비교 대상과 경계

- Chat Completions: `openai/gpt-6-luna`, `anthropic/claude-haiku-5.5`
- Decisions: `typesafe/jev-1.14`
- 공통 출력: `question_type`, `required_evidence`, `next_action`, `reason_code`
- 공통 입력 경계: `user_request`, `current_state`, `external_material`
- Jev는 5개 typed question을 사용하므로 Chat과 요청 바이트가 같다고 보지 않습니다. 공통 의미 계약과 13건의 상태만 같습니다.
- 외부 자료는 지시가 아니라 데이터입니다. 프롬프트 인젝션의 상세 방어 설계는 V0 다음 작업입니다.

## 연결된 파일

- [Supervisor prompt](../../backend/prompts/supervisor_v0.md)
- [13건 상태 표본](../samples/supervisor_prompt_v0.jsonl)과 [무결성 기록](../samples/supervisor_prompt_v0_frozen.json)
- [Chat 실행기](../runners/run_supervisor_prompt_v0.py), [Jev 실행기](../runners/run_supervisor_prompt_v0_jev.py), [통합 집계기](../runners/compare_supervisor_prompt_v0.py)

## 실행 순서

1. `uv run --no-sync python -m evals.runners.run_supervisor_prompt_v0 plan .tmp/supervisor-v0-chat-plan`
2. `uv run --no-sync python -m evals.runners.run_supervisor_prompt_v0_jev plan .tmp/supervisor-v0-jev-plan`
3. 아래 오프라인 테스트를 실행합니다.
4. live 실행의 정확한 모델·provider, 최악 호출 수, 모델별·전체 비용 상한과 중단 조건을 제시하고 사용자에게 별도 승인을 받습니다.
5. 정확한 모델/provider마다 `--provider`를 지정해 1건 smoke를 실행합니다. 본 실행은 이 smoke에 기록된 model·provider를 고정하며 smoke가 없거나 metadata가 달라지면 시작하지 않습니다.
6. 13건 V0 표본을 실행합니다.
7. 세 결과의 `dataset_sha256`과 `contract_sha256`, case 집합이 모두 같을 때만 집계합니다.

```powershell
uv run --no-sync pytest tests/graph/test_graph_supervisor.py tests/evals/test_supervisor_prompt_v0_common.py tests/evals/test_supervisor_prompt_v0.py tests/evals/test_supervisor_prompt_v0_jev.py tests/evals/test_compare_supervisor_prompt_v0.py -q
```

## live gate

`plan`과 pytest는 외부 모델을 호출하지 않습니다. `smoke`와 `run`에는 `--confirm-live`와 양수 상한이 필요하며 `OPENROUTER_API_KEY`만 사용합니다. Chat 실행은 `EvaluationBudget`으로 호출·시간·예약 비용을 제한합니다. Decisions 응답이 집행 가능한 비용을 보고하지 않으므로 Jev의 `--max-usd`는 승인 기록이고, 결과에는 `Not Reported` 및 `usd_cap_technically_enforced=false`를 남깁니다.

이 V0 구현 과정에서는 live 모델 호출을 하지 않았습니다. 이후의 실제 실행 기록이 별도로 남기기 전에는 세 모델의 V0 품질 결과나 최종 선택 결론으로 해석하지 않습니다.
