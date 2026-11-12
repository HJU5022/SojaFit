# DB ERD

<!-- 자동 생성: scripts/db/gen_schema_docs.py. 직접 고치지 않는다(표 설명은 그 파일의 TABLES, 구조는 DB). -->

- 실제 DB에서 읽은 서비스 표의 그림이다. **모든 선이 DB의 FK**이고, 선 이름은 `FK 칸 (ON DELETE 규칙)`이다. 표마다 하는 일 · 칸 설명은 [table-definition.md](table-definition.md).
- `agent_*`는 `sojafit_agent` 스키마의 표를 줄여 쓴 이름이다(`public`과 이름이 같은 표가 있어서). `PK` 기본 키, `FK` 외래 키, `UK` 단독 UNIQUE 칸.

```mermaid
erDiagram
    agent_threads ||--o{ agent_analysis_events : "thread_id (CASCADE)"
    agent_threads ||--o{ agent_messages : "thread_id (CASCADE)"
    approvals ||--o{ quotes : "approval_id+user_id (CASCADE)"
    approvals ||--o| approved_cases : "approval_id+user_id (CASCADE)"
    messages ||--o| approvals : "message_id (CASCADE)"
    projects ||--o{ threads : "project_id (CASCADE)"
    projects ||--o| circuits : "project_id (CASCADE)"
    runs ||--o{ messages : "run_id+thread_id (CASCADE)"
    threads ||--o{ messages : "thread_id (CASCADE)"
    threads ||--o{ runs : "thread_id (CASCADE)"
    threads ||--o| agent_threads : "id (CASCADE)"
    users ||--o{ agent_analysis_usage : "user_id (CASCADE)"
    users ||--o{ agent_threads : "user_id (CASCADE)"
    users ||--o{ approvals : "user_id (CASCADE)"
    users ||--o{ approved_cases : "user_id (CASCADE)"
    users ||--o{ auth_sessions : "user_id (CASCADE)"
    users ||--o{ projects : "user_id (CASCADE)"
    users ||--o{ quotes : "user_id (CASCADE)"
    users ||--o| auth_google_identities : "user_id (CASCADE)"

    users {
        bigint id PK
        varchar(100) login_id UK
        varchar(255) password_hash
        bool is_active
        timestamptz created_at
        timestamptz updated_at
        text role
    }
    auth_sessions {
        char(64) token_hash PK
        bigint user_id FK
        timestamptz expires_at
        timestamptz last_seen_at
    }
    auth_login_attempts {
        char(64) login_hash PK
        int failed_count
        timestamptz locked_until
        timestamptz window_started_at
    }
    auth_login_ip_attempts {
        char(64) ip_hash PK
        int failed_count
        timestamptz window_started_at
        timestamptz locked_until
    }
    auth_signup_attempts {
        char(64) ip_hash PK
        date day PK
        int signup_count
    }
    auth_google_states {
        text state_hash PK
        text browser_hash
        text verifier
        text nonce
        timestamptz expires_at
    }
    auth_google_identities {
        text issuer PK
        text subject PK
        bigint user_id FK, UK
    }
    projects {
        bigint id PK
        bigint user_id FK
        text name
        text source_kind
        text demo_id
        timestamptz created_at
        timestamptz updated_at
    }
    circuits {
        bigint project_id PK, FK
        jsonb connections
        text source_sha256
        text parser_version
        timestamptz created_at
    }
    threads {
        uuid id PK
        bigint project_id FK
        timestamptz created_at
    }
    runs {
        uuid id PK
        uuid thread_id FK
        text status
        jsonb safe_result
        timestamptz created_at
        timestamptz updated_at
    }
    messages {
        bigint id PK
        uuid thread_id FK
        uuid run_id FK
        text role
        text content
        timestamptz created_at
    }
    approvals {
        bigint id PK
        bigint user_id FK
        bigint message_id FK, UK
        text candidate_part
        text verdict
        text part_number
        jsonb snapshot
        timestamptz created_at
    }
    quotes {
        bigint id PK
        bigint user_id FK
        bigint approval_id FK
        text part_number
        int quantity
        timestamptz created_at
    }
    approved_cases {
        bigint id PK
        bigint user_id FK
        bigint approval_id FK, UK
        timestamptz created_at
    }
    app_migrations {
        text version PK
        timestamptz applied_at
        text note
    }
    agent_threads {
        uuid id PK, FK
        bigint user_id FK
        text target
        int version
        int retries
        text status
        timestamptz created_at
        jsonb input_record
    }
    agent_messages {
        bigint id PK
        uuid thread_id FK
        text role
        text checkpoint_id
        text content
        timestamptz created_at
    }
    agent_analysis_events {
        uuid id PK
        uuid thread_id FK
        int version
        text request_id
        text mode
        text status
        int elapsed_ms
        jsonb stages
        text trace_id
        text trace_delivery
        timestamptz created_at
    }
    agent_analysis_usage {
        bigint user_id PK, FK
        date day PK
        numeric(16,10) reserved_usd
        int attempts
        timestamptz next_allowed
        bigint reserved_tokens
    }
    agent_analysis_service_usage {
        date day PK
        bigint reserved_tokens
    }
```

## 선이 없는 표

- 다른 표와 FK가 없다(해시 키 · 날짜 키로만 식별): `public.auth_login_attempts` · `public.auth_login_ip_attempts` · `public.auth_signup_attempts` · `public.auth_google_states` · `public.app_migrations` · `sojafit_agent.analysis_service_usage`

## 코퍼스 · LangGraph 표(이 문서 범위 밖)

서비스 표가 아니라 이 문서의 그림 · 정의에 넣지 않는다. 이름만 적는다.

- 코퍼스(`public`, `db/002` · `009`): `source_documents` · `document_chunks` · `chunk_embeddings` · `chunk_embedding_bits`
- LangGraph 라이브러리(`sojafit_agent`, `PostgresSaver` · `PostgresStore`가 만든다): `checkpoints` · `checkpoint_blobs` · `checkpoint_writes` · `checkpoint_migrations` · `store` · `store_vectors` · `store_migrations` · `vector_migrations`
