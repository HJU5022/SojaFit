# DB ERD

## 기본 규칙

- 표를 만들거나 바꾸는 SQL PR에서 이 문서도 같이 고칩니다.
- 열의 정본은 SQL입니다. 여기에는 표마다 하는 일 한 줄과 만드는 곳만 적습니다.
- 우리가 만드는 표와 라이브러리가 만드는 표를 나눠 적습니다.

## 그림

표가 정해지면 mermaid `erDiagram`으로 그립니다.

## 우리가 만드는 표

| 표 | 하는 일 | 만드는 SQL |
|---|---|---|
| (정할 것) | | |

SPEC에서 나오는 후보는 로그인 사용자, 코퍼스 청크와 벡터, 승인된 견적서입니다. 이름과 열은 SPEC 4절에서 계약을 정한 뒤 적습니다.

## 라이브러리가 만드는 표

`langgraph-checkpoint-postgres` 3.2.0의 `setup()`이 만듭니다. 우리 SQL에서 만들지 않습니다.

| 표 | 만드는 곳 | 하는 일 |
|---|---|---|
| `checkpoints` | `PostgresSaver` | thread별 그래프 상태(체크포인트) |
| `checkpoint_blobs` | `PostgresSaver` | 체크포인트의 채널 값 |
| `checkpoint_writes` | `PostgresSaver` | 재개할 때 쓰는 노드의 중간 쓰기 |
| `checkpoint_migrations` | `PostgresSaver` | 체크포인트 스키마 버전 |
| `store` | `PostgresStore` | 사용자별 장기 기억. namespace는 `("memories", user_id)`(`backend/memory.py`) |
| `store_vectors` | `PostgresStore` | 기억의 임베딩(인덱스를 설정할 때) |
| `store_migrations`, `vector_migrations` | `PostgresStore` | Store 스키마 버전 |
