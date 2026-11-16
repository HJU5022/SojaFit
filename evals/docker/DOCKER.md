# docker

## 역할
- 이 폴더: 평가 실험을 돌리는 컨테이너 이미지 정의를 둔다. 저장소 루트의 `Dockerfile`(서비스 이미지)과는 별개다.
- 넣는 것: `Dockerfile.<용도>`. 원격 GPU(RTX 3080 Ti, WSL2 Docker)에서 로컬 임베딩 모델과 실험 DB를 쓰는 평가용 이미지.
- 넣지 않는 것: 서비스 이미지(루트 `Dockerfile`, `docker-compose.yml`), 실행 코드(`evals/runners/`), 실험 DB 데이터와 모델 가중치(저장소 밖).
- 담당: 평가·문서

## 파일

| 파일 | 유형 | 설명 |
|---|---|---|
| `DOCKER.md` | 폴더 설명 | 이 문서 |
| `Dockerfile.gpu_embed` | 이미지 정의 | torch(CUDA)·sentence-transformers. 로컬 임베딩 모델 실험용(preregister #7·#8) |
| `Dockerfile.embedding_grid` | 이미지 정의 | 임베딩 격자 본평가(preregister #16) 실행 이미지. 바탕 이미지 `sojafit-emb`에 `psycopg`·`pgvector`·`rank-bm25`·`openai`·`voyageai`를 더함 |

## 쓰는 법

1. 이미지를 만든다: `docker build -t sojafit-emb -f evals/docker/Dockerfile.gpu_embed evals/docker`, 이어서 `docker build -t sojafit-embed-run -f evals/docker/Dockerfile.embedding_grid evals/docker`.
2. 같은 네트워크에 pgvector 0.8 이상 PostgreSQL 16 컨테이너(실험 DB, 앱 DB와 별개)를 띄우고 `EMBED_DB`에 그 주소를 준다.
3. 저장소를 `/work/repo`, 코퍼스 `chunks.jsonl`을 `/work/data`, 빈 폴더를 `/work/logs`·`/work/out`으로 마운트하고 `cd /work/repo` 뒤 차례로 실행한다: `python -m evals.runners.embed_cards load /work/data/chunks.jsonl`, `python -m evals.runners.embed_cards <모델 키>`, `python -m evals.runners.run_embedding_grid <결과 이름>`. `/work/repo/COMMIT` 파일에 측정 커밋 해시를 적어 두면 결과 meta에 남는다.
4. 결과 `/work/out/<결과 이름>.json`은 [evals/results/embedding/](../results/embedding/)에 `grid_<날짜>.json`으로 옮긴다.

## 한계

- 위 절차는 다시 돌려 확인하지 않았다.
- `sojafit-emb`가 `Dockerfile.gpu_embed`로 만든 이미지라는 것은 `Dockerfile.embedding_grid` 머리 주석에만 있다. 태그는 빌드 명령이 정하므로 당시 빌드 기록으로는 확인하지 못했다.
