# extras

## 역할
- 이 폴더: 가산 중 이미지에 들어가지 않는 작업(학습)을 둡니다. Dockerfile은 이 폴더를 복사하지 않습니다. 지금은 하위 폴더 `finetune/`의 설명 파일만 있습니다.
- 넣는 것: 파인튜닝 학습 코드와 비교 결과(`finetune/`).
- 넣지 않는 것: 서비스 안에서 돌아야 하는 가산. MCP 서버와 Skill은 `backend/mcp_skill/`, 그래프 검색(GraphRAG)과 증분 수집 자동화는 `backend/rag/`에 둡니다.
- 담당: 가산을 시작할 때 정합니다

## 파일
- `finetune/` — 파인튜닝. 비어 있고 설명 파일만 있습니다. [FINETUNE.md](finetune/FINETUNE.md)
