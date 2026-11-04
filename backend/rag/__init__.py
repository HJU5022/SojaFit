"""RAG 파이프라인 패키지: 수집(collect)·파싱(parse)·청킹(chunk)·적재(ingest)는 오프라인 도구, 검색(retrieve)은 서버가 import한다.

- 역할: 데이터시트 PDF를 청크로 만들어 DB에 넣고(오프라인), 질문에 맞는 청크를 찾는다(`retrieve`).
- 하지 않는 일: 답 생성·채점(`backend/graph/`), 숫자 비교 판정(`backend/judge/`).
- 출처: docs/specs/rag-pipeline.md, backend/rag/RAG.md.
"""
