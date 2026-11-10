# eval

## 역할
- 이 폴더: 평가 결과 파일을 사람 손 작업과 이어 주는 변환 스크립트를 둡니다. 저장소 루트에서 실행합니다.
- 넣는 것: 사람 채점 시트 같은 외부 입력을 평가 JSONL로 되돌리는 스크립트.
- 넣지 않는 것: 평가 실행 · 채점 · 동결 스크립트와 결과(`evals/`), 시험(`tests/evals/`).
- 담당: 에이전트

## 파일
- `EVAL.md` — 이 문서
- `import_human_review.py` — 사람 채점 시트(마크다운 O/X 표)를 인젝션 실측 JSONL의 `human_review` 칸으로 옮긴 새 사본을 쓰고, assistant 잠정 분류와 사람 판정의 일치율을 출력한다(원본 수정 없음)

## 실행

```bash
uv run python scripts/eval/import_human_review.py <시트.md> --out <새.jsonl> --reviewer <이름> [--jsonl <원본.jsonl>]
```

`--jsonl` 기본값은 실측03 파일이다. `--out`이 원본과 같으면 멈춘다. 시트에서 `판정`이 비어 있는 항목은 건너뛴다.
