# samples

## 역할
- 이 폴더: v1·v2 동결 평가셋이 아닌 보조 표본을 둡니다. 임베딩 프록시와 수퍼바이저 V0 후보 비교 입력이 있습니다.
- 넣는 것: 프록시·프로토타입 비교 표본(jsonl)과 해당 표본 전용 무결성 기록(json).
- 넣지 않는 것: 동결 평가셋·동결 기록(`evals/`의 `dataset_v1.jsonl`, `FROZEN.json`), 동결 전 초안(`evals/drafts/`), 표본으로 잰 결과(`evals/results/embedding/`).
- 담당: 평가

## 파일
- `SAMPLES.md` — 이 문서
- `v3_50_codex_paste.md` — v3 50문항 비교에 사용한 입력 원본
- `embedding_sample_v0.jsonl` — 임베딩 후보를 거르는 비동결 프록시 표본(30청크·18질의, 48행). v1·v2나 G5 건수에 포함하지 않고 `evals/runners/benchmark_embeddings.py`가 읽음
- `retrieval_r1.jsonl` — 검색 표본 84문항(사전 등록 #25). 정답 페이지는 사양 표 행이 있는 쪽으로 정하고(사람 판정 없음), 질문은 사용자 말투로 자동 초안을 쓴 뒤 기계 검사 · 자동 O/X 검사를 통과한 것만 남김. 무리 G1 단서 많음 · G2 단서 적음 · G3 근거 두 쪽 · G4 품번 없음, `split` dev 세트/test 세트는 PDF 단위. 만든 스크립트는 저장소 밖 `전자_데이터시트/evidence/r1/`(make_items.py · gen_questions.py)
- `retrieval_r1_rewrite_q3.json` — 같은 84문항의 고정 재작성 질의 Q3(서비스 `rewrite()` 출력 그대로). `evals/runners/run_retrieval_r1.py rewrite`가 만듦
- `supervisor_prompt_v0.jsonl` — 수퍼바이저 V0 세 후보를 같은 조건에서 비교하는 13건. 같은 사용자 요청의 회로·데이터시트·승인 사례 확보 전후와 재시도 소진 상태를 포함하며 v1·v2에는 포함하지 않음
- `supervisor_prompt_v0_frozen.json` — 위 13건의 sha256·건수. 후보별 실행 입력이 달라지는 것을 막는 표본 전용 무결성 기록이며 루트 `FROZEN.json`의 v1·v2 동결을 바꾸지 않음
