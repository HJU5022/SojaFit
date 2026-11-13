# v4h 코퍼스 지문 (D10 · 2026-11-12)

출처: 저장소 `evals/results/chunking/v4h-2026-11-08/` (D9 이관). 청크 본문 jsonl은 lab에만 있고 저장소에는 없다.

## summary.json 숫자

| 키 | 값 |
|---|---|
| `chunker_version` | `tsc-v4h-2026-11-08` |
| `cards` | 51,967 |
| `distinct_text` | 51,967 |

게이트 “서로 다른 청크 1만 개”는 `distinct_text`로 충족. 운영 DB에서 `sha256(본문)`을 다시 센 값은 아님(`docs/GATES.md` G3).

## 결과 파일 sha256

`evals/results/chunking/v4h-2026-11-08/SHA256.txt`와 동일(11-12에 파일 존재 확인).

```
426b44750dc6aae3634855da44b5a9de675fdc31fb9ee859fc55d772a8c0d786  evals/results/chunking/v4h-2026-11-08/manifest.jsonl
7240f78dd060d68d713d9be8b9404254724d9d911139f7e80aa86109d236723b  evals/results/chunking/v4h-2026-11-08/summary.json
29bfd52b0d40df34c81c9cc526292ca6df2ef55ad9f5af361d53aac5cda7fb95  evals/results/chunking/v4h-2026-11-08/table_suspects.jsonl
```

판정진단 묶음 해시는 같은 `SHA256.txt` 앞부분(judge-diagnosis)을 본다.
