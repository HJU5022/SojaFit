# 현재(as-is) ERD

- 기준: 운영 DB 구조(11-10 밤). 표 정의서: [`tables.md`](tables.md).
- **실선(`||--o{`)은 DB의 FK**, **점선(`||..||`)은 FK가 없고 같은 UUID로만 논리적으로 묶인 관계**다.
- 범위 밖(그림에서 뺀 것): 코퍼스 4표(`source_documents` → `document_chunks` → `chunk_embeddings` · `chunk_embedding_bits`), LangGraph 체크포인트 표(`sojafit_agent.checkpoints` · `checkpoint_blobs` · `checkpoint_writes`, `thread_id`가 text라 FK 없음).

## 1. 전체 그림

```mermaid
erDiagram
    users ||--o{ auth_sessions : "세션"
    users ||--o| auth_google_identities : "Google 연결"
    users ||--o{ projects : "소유"
    projects ||--|| circuits : "정규화 회로(1:1)"
    projects ||--o{ threads : "대화"
    threads ||--o{ runs : "질문 실행"
    threads ||--o{ messages : "메시지"
    runs ||--o{ messages : "run의 메시지"
    messages ||--o| approvals : "승인(메시지당 1건)"
    users ||--o{ approvals : "승인자"
    approvals ||--o| quotes : "견적(승인당 1건)"
    approvals ||--o| approved_cases : "승인 사례"
    users ||--o{ quotes : "소유"
    users ||--o{ approved_cases : "소유"

    threads ||..|| agent_threads : "같은 UUID (FK 없음)"
    circuits ||..o{ agent_circuits : "connections 복사 (FK 없음)"
    users ||--o{ agent_circuits : "RESTRICT"
    users ||--o{ agent_threads : "RESTRICT"
    agent_circuits ||--o{ agent_threads : "circuit_id (RESTRICT)"
    agent_threads ||--o{ agent_messages : "분석 문맥"
    agent_threads ||--o{ agent_approvals : "죽은 경로 (0행)"
    agent_threads ||--o{ analysis_events : "운영 기록"
    users ||--o{ analysis_usage : "하루 사용량"

    users {
        bigint id PK
        varchar login_id UK
        varchar password_hash
        varchar display_name "미사용"
        bool is_active
        text role
    }
    projects {
        bigint id PK
        bigint user_id FK
        text name
        text source_kind
        text demo_id "CHECK: 6개 이름 목록"
    }
    circuits {
        bigint project_id PK "FK"
        jsonb connections
        text source_sha256
    }
    threads {
        uuid id PK
        bigint project_id FK
    }
    runs {
        uuid id PK
        uuid thread_id FK
        text status
        jsonb safe_result "CHECK: JSON 모양 재귀 검사"
    }
    messages {
        bigint id PK
        uuid thread_id FK
        uuid run_id FK
        text role
        text content
    }
    approvals {
        bigint id PK
        bigint user_id FK
        bigint message_id UK
        jsonb snapshot "3벌 중 1"
    }
    quotes {
        bigint id PK
        bigint approval_id FK
        text part_number
        jsonb snapshot "3벌 중 2, 읽는 곳 없음"
    }
    approved_cases {
        bigint id PK
        bigint approval_id UK
        jsonb snapshot "3벌 중 3"
    }
    agent_circuits {
        uuid id PK "대화 UUID와 같은 값"
        bigint user_id FK
        text netlist "전부 빈 글자"
        jsonb connections "public 복사본"
    }
    agent_threads {
        uuid id PK "public.threads.id와 같은 값"
        bigint user_id FK
        uuid circuit_id FK
        text status
        int version
        jsonb input_record
    }
    agent_messages {
        bigint id PK
        uuid thread_id FK
        text role
        text content
    }
    agent_approvals {
        uuid thread_id FK
        int version
        jsonb snapshot "0행"
    }
```

> 그림의 `agent_*`는 `sojafit_agent.*` 스키마의 표다(mermaid 이름 규칙 때문에 접두로 줄였다).

## 2. 인증 표 (그림 1에서 뺀 것)

```mermaid
erDiagram
    users ||--o{ auth_sessions : "FK CASCADE"
    users ||--o| auth_google_identities : "FK CASCADE, 사용자당 1개"
    auth_google_states { text state_hash PK }
    auth_google_pending { text request_id PK "11-10 이후 안 쓰는 표" }
    auth_login_attempts { char login_hash PK "계정별 실패 · 잠금" }
    auth_login_ip_attempts { char ip_hash PK "IP별 실패 · 잠금" }
    auth_signup_attempts { char ip_hash PK "DEMO_MODE=1에서만" }
```

앞의 네 표(`auth_google_states` · `auth_google_pending` · `auth_login_attempts` · `auth_login_ip_attempts` · `auth_signup_attempts`)는 `users`와 FK가 없다(해시 키로만 식별, 사용자가 없어도 쌓이는 방어 장치).

## 3. 읽는 법: 지금 구조의 핵심 문제 4개

| 번호 | 그림에서 보이는 것 | 의미 |
|---|---|---|
| ① | 점선 2개(`threads`↔`agent_threads`, `circuits`↔`agent_circuits`) | 같은 대화 · 회로가 두 스키마에 있고 DB가 연결을 보장하지 않음 |
| ② | `snapshot`이 `approvals` · `quotes` · `approved_cases`에 | 같은 JSON이 3벌 |
| ③ | `agent_approvals`(0행)와 `auth_google_pending` | 부르는 코드가 없는 표 |
| ④ | `agent_*`의 FK가 `RESTRICT` | 계정 · 프로젝트 삭제는 코드가 분석 기록을 먼저 지워야 하고, DB는 그 순서를 강제하지 못함 |
