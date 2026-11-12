# 임베딩 후보 라이선스와 공개 범위

- 상태: 현행 (라이선스·공개 범위 분류). 후보 표는 2026-11-02 조사 시점 값이며 현재 서비스 임베딩은 후보 표에 없다
- 기준일: 2026-11-02 (후보 표), 현재 서비스 값 확인 2026-11-12
- 정본 여부: 정본(임베딩 후보의 라이선스 분류와 저장소 공개 범위)
- 관련 문서: [후보별 조사](embedding-candidate-investigation.md), [ADR 0004](../adr/0004-임베딩-1536차원은-임시-결정.md), [SPEC](../../SPEC.md) 6절, [EVAL_REPORT](../../EVAL_REPORT.md) 1-4장

법률 자문이 아니다. 상용 배포 전에는 고정 revision의 원문 라이선스와 서비스 약관을 다시 검토한다. 이 문서에는 후보·라이선스 조사만 있고 평가기 구현, 원시 결과, 모델 캐시, 가중치는 없다.

## 현재 서비스 임베딩

| 항목 | 값 | 근거 |
|---|---|---|
| 모델 | Voyage API `voyage-4-large`, 1024차원 | `backend/rag/retrieve.py:29-30` |
| 후보 표 | 현재 서비스 모델은 아래 13종 조사표에 없다. 조사 당시(2026-11-02) 서비스 기본값은 `text-embedding-3-small` API였다 | [ADR 0004](../adr/0004-임베딩-1536차원은-임시-결정.md) |
| 운영 전 확인 | Voyage의 최신 서비스 약관, 데이터 보관·학습 사용, ZDR, 지역, 재위탁 조건을 현재 endpoint 기준으로 확인 | 미확인 |
| 별도 추론 서버 배포 시 | 가중치 라이선스와 배포물 고지 의무, 이미지·서버 보안이 별도로 적용된다 | |

## 후보 라이선스 분류 (2026-11-02)

| 모델 | 고정 revision | 공식 라이선스/약관 | 분류 | 가중치 GitHub 포함 | 확인 출처 |
|---|---|---|---|---|---|
| `text-embedding-3-small` | 해당 없음(API) | OpenAI/OpenRouter 서비스 약관 | 상업 후보·API 기준선 | 해당 없음 | [OpenAI Services Agreement](https://openai.com/policies/services-agreement/), [OpenRouter Terms](https://openrouter.ai/terms), [Privacy](https://openrouter.ai/privacy/) |
| `voyageai/voyage-4` | 해당 없음(OpenRouter API) | OpenRouter 서비스 약관 | 상업 후보·API 실행 | 해당 없음 | [OpenRouter 모델 페이지](https://openrouter.ai/voyageai/voyage-4), [OpenRouter Terms](https://openrouter.ai/terms), [ZDR](https://openrouter.ai/docs/guides/features/zdr), [Providers](https://openrouter.ai/providers/) |
| `voyageai/voyage-4-nano` | `5fb34e870f49f19e79c94d5e118f5ee730133279` | Apache-2.0 | 상업 후보·로컬 실행, 원격 코드 검토 필요 | 아니오 | [고정 revision 모델 카드](https://huggingface.co/voyageai/voyage-4-nano/tree/5fb34e870f49f19e79c94d5e118f5ee730133279) |
| `BAAI/bge-m3` | `5617a9f61b028005a4858fdac845db406aefb181` | MIT | 상업 후보·실행 | 아니오 | [고정 revision 모델 카드](https://huggingface.co/BAAI/bge-m3/tree/5617a9f61b028005a4858fdac845db406aefb181) |
| `nlpai-lab/KURE-v1` | `8b418a58414668e75532ed045c22d9ca018ae2b2` | MIT | 상업 후보·실행 | 아니오 | [고정 revision](https://huggingface.co/nlpai-lab/KURE-v1/tree/8b418a58414668e75532ed045c22d9ca018ae2b2), [모델 카드](https://huggingface.co/nlpai-lab/KURE-v1) |
| `Qwen/Qwen3-Embedding-0.6B` | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | Apache-2.0 | 상업 후보·실행 | 아니오 | [고정 revision 모델 카드](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/tree/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3) |
| `Alibaba-NLP/gte-multilingual-base` | `9bbca17d9273fd0d03d5725c7a4b0f6b45142062` | Apache-2.0 | 상업 후보·실행, 원격 코드 검토 필요 | 아니오 | [고정 revision 모델 카드](https://huggingface.co/Alibaba-NLP/gte-multilingual-base/tree/9bbca17d9273fd0d03d5725c7a4b0f6b45142062) |
| `intfloat/multilingual-e5-large-instruct` | `274baa43b0e13e37fafa6428dbc7938e62e5c439` | MIT | 상업 후보·실행 | 아니오 | [고정 revision 모델 카드](https://huggingface.co/intfloat/multilingual-e5-large-instruct/tree/274baa43b0e13e37fafa6428dbc7938e62e5c439) |
| `jinaai/jina-embeddings-v3` | `ab036b023d30b4d1138c4c3bfa9f0c445ab455d6` | CC BY-NC 4.0 | 연구용 실행만·상업 후보 제외 | 아니오 | [고정 revision](https://huggingface.co/jinaai/jina-embeddings-v3/tree/ab036b023d30b4d1138c4c3bfa9f0c445ab455d6), [모델 카드](https://huggingface.co/jinaai/jina-embeddings-v3) |
| `nomic-ai/nomic-embed-text-v2-moe` | `1066b6599d099fbb93dfcb64f9c37a7c9e503e85` | Apache-2.0 | 상업 후보·실행, 원격 코드 검토 필요 | 아니오 | [고정 revision 모델 카드](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe/tree/1066b6599d099fbb93dfcb64f9c37a7c9e503e85) |
| `Snowflake/snowflake-arctic-embed-m-v2.0` | `95c2741480856aa9666782eb4afe11959938017f` | Apache-2.0 | 상업 후보·실행, 원격 코드 검토 필요 | 아니오 | [고정 revision 모델 카드](https://huggingface.co/Snowflake/snowflake-arctic-embed-m-v2.0/tree/95c2741480856aa9666782eb4afe11959938017f) |
| `google/embeddinggemma-300m` | `57c266a740f537b4dc058e1b0cda161fd15afa75` | Gemma 약관·접근 동의 필요 | 조사 전용·실행 제외 | 아니오 | [고정 revision 모델 카드](https://huggingface.co/google/embeddinggemma-300m/tree/57c266a740f537b4dc058e1b0cda161fd15afa75) |
| `jinaai/jina-embeddings-v4` | `853c867b65b749f3c3c72a06868140d842e04f06` | Qwen Research License | 조사 전용·상업 후보 제외·약 7.89GB | 아니오 | [고정 revision 모델 카드](https://huggingface.co/jinaai/jina-embeddings-v4/tree/853c867b65b749f3c3c72a06868140d842e04f06), [라이선스](https://huggingface.co/jinaai/jina-embeddings-v4/blob/853c867b65b749f3c3c72a06868140d842e04f06/LICENSE) |

`voyageai/voyage-4-lite`는 2026-11-02 현재 OpenRouter에 $0.02/M tokens·32K context로 표시되는 미평가 API 후보이며, 위 13종 조사표에는 아직 포함하지 않는다. Nano의 로컬 점수를 Lite에 이전하지 않고 추가 시험을 승인받은 경우 별도 후보로 등록한다: [OpenRouter 모델 페이지](https://openrouter.ai/voyageai/voyage-4-lite).

## GitHub에 올리는 것과 올리지 않는 것

저장소 공개 대상으로는 후보 ID, 고정 revision, 검수된 다운로드·재현 명령, 입력 계약, 라이선스 분류, 실행 환경과 결과 메타데이터를 둘 수 있다. 이번 문서 변경에는 그중 조사·계약 문서만 포함한다. API 키, Hugging Face 토큰, 모델 캐시, 가중치 파일, Docker layer에 포함된 가중치는 올리지 않는다.

MIT와 Apache-2.0 후보는 상업적 이용 후보로 둘 수 있지만 라이선스 의무가 사라지는 것은 아니다. 외부 관리형 API로 확정하면 가중치를 배포하지 않지만, 자체 추론 API로 확정하면 모델 가중치를 Docker 이미지나 배포 산출물에 포함할 수 있으므로 해당 고정 revision의 LICENSE와 필요한 NOTICE·저작권 고지를 이미지 또는 배포물에 함께 포함한다.

CC BY-NC 4.0의 Jina v3와 Qwen Research License의 Jina v4는 상업 후보에서 제외한다. 연구 결과표에는 비상업·연구용이라는 사실을 명시한다. EmbeddingGemma는 Gemma 약관 동의와 재배포 조건을 별도로 검토하기 전까지 조사 전용으로 유지한다.

## 원격 코드 고정

`trust_remote_code=True` 후보는 모델 revision만 고정해도 `config.json`이 다른 코드 저장소를 가리킬 수 있다. 실행 결과에는 아래 `code_revision`도 함께 기록한다.

| 모델 | 코드 저장소 | 고정 code revision |
|---|---|---|
| `Alibaba-NLP/gte-multilingual-base` | `Alibaba-NLP/new-impl` | `40ced75c3017eb27626c9d4ea981bde21a2662f4` |
| `jinaai/jina-embeddings-v3` | `jinaai/xlm-roberta-flash-implementation` | `bd55a5ec8e6c0fb1d6c26efb4b6a4a74ce8a88d3` |
| `nomic-ai/nomic-embed-text-v2-moe` | `nomic-ai/nomic-bert-2048` | `7710840340a098cfb869c4f65e87cf2b1b70caca` |
| `Snowflake/snowflake-arctic-embed-m-v2.0` | 모델 저장소 내부 코드 | `95c2741480856aa9666782eb4afe11959938017f` |
| `voyageai/voyage-4-nano` | 모델 저장소 내부 코드 | `5fb34e870f49f19e79c94d5e118f5ee730133279` |

위 코드의 외부 프로세스·네트워크·동적 실행 패턴 정적 검색 결과: Jina v3의 파일 읽기·쓰기 외에 점검 패턴은 없었다. 보안 감사가 아니라 실행 전 최소 점검이다. 검색 결과 원본은 저장소에 없다.
