# 목표(to-be) ERD

- 기준: [`baseline_service.sql`](sql/baseline_service.sql). 표 정의서는 [`tables.md`](tables.md), 현재 구조는 [`../as-is/erd.md`](../as-is/erd.md).
- **모든 선이 DB의 FK다.** 현재 구조의 점선(같은 UUID로만 묶임)이 사라졌고, `sojafit_agent.*`의 FK는 전부 `CASCADE`다.
- `agent_*`는 `sojafit_agent.*` 스키마의 표를 그림 이름 규칙 때문에 줄여 쓴 것이다.

## 1. 추천안(P1 + P2): 서비스 표 전체

```mermaid
erDiagram
    users ||--o{ auth_sessions : "세션(CASCADE)"
    users ||--o| auth_google_identities : "Google 연결(CASCADE)"
    users ||--o{ projects : "소유(CASCADE)"
    projects ||--|| circuits : "정규화 회로, 유일한 사본"
    projects ||--o{ threads : "대화"
    threads ||--o{ runs : "질문 실행"
    threads ||--o{ messages : "화면 메시지"
    runs ||--o{ messages : "run의 메시지"
    messages ||--o| approvals : "승인(메시지당 1건)"
    users ||--o{ approvals : "승인자"
    approvals ||--o{ quotes : "견적"
    approvals ||--o| approved_cases : "승인 사례 표시 행"
    users ||--o{ quotes : "소유"
    users ||--o{ approved_cases : "소유"

    threads ||--|| agent_threads : "같은 UUID, FK CASCADE (신규)"
    users ||--o{ agent_threads : "소유(CASCADE)"
    agent_threads ||--o{ agent_messages : "분석 문맥"
    agent_threads ||--o{ analysis_events : "운영 기록"
    users ||--o{ analysis_usage : "하루 사용량(CASCADE)"

    users {
        bigint id PK
        varchar login_id UK
        varchar password_hash
        bool is_active
        text role
    }
    projects {
        bigint id PK
        bigint user_id FK
        text name
        text source_kind
        text demo_id "데모일 때만 값 (단순 CHECK)"
    }
    circuits {
        bigint project_id PK
        jsonb connections "연결의 유일한 사본"
    }
    threads {
        uuid id PK
        bigint project_id FK
    }
    runs {
        uuid id PK
        uuid thread_id FK
        text status
        jsonb safe_result "필수 키 6개만 검사"
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
        text candidate_part "신규: 표시 이름"
        text verdict "신규"
        text part_number "신규: 식별 품번"
        jsonb snapshot "스냅샷의 유일한 사본"
    }
    quotes {
        bigint id PK
        bigint approval_id FK
        text part_number
        int quantity
    }
    approved_cases {
        bigint id PK
        bigint approval_id UK
    }
    agent_threads {
        uuid id PK "public.threads.id와 같음, FK"
        bigint user_id FK
        text target
        int version
        text status
        jsonb input_record
    }
    agent_messages {
        bigint id PK
        uuid thread_id FK
        text role
        text content
    }
    analysis_events {
        uuid id PK
        uuid thread_id FK
    }
    analysis_usage {
        bigint user_id PK
        date day PK
    }
```

### 그림에 없는 것
- 인증 보조 표(`auth_login_attempts` · `auth_login_ip_attempts` · `auth_signup_attempts` · `auth_google_states`)와 `analysis_service_usage` · `app_migrations`는 다른 표와 FK가 없다(해시 키 · 날짜 키로만 식별).
- **LangGraph 체크포인트 3표**(`sojafit_agent.checkpoints` · `checkpoint_blobs` · `checkpoint_writes`)는 `thread_id`가 글자라 FK를 걸 수 없다. 대신 **`public.threads`의 BEFORE DELETE 트리거**(`trg_threads_purge_checkpoints`)가 대화 행이 지워질 때 같이 지운다. 프로젝트 · 계정 삭제의 cascade, 보관 기간 청소, 운영자의 직접 삭제 어느 경로든 같다.
- 사라진 표: `sojafit_agent.circuits`(분석 회로 사본), `sojafit_agent.approvals`(죽은 승인 경로), `public.auth_google_pending`(승인 대기, 선택 단계 2b).

## 2. 삭제의 흐름(목표)

```mermaid
flowchart TD
    U[사용자 삭제 / 탈퇴] --> P[projects 삭제]
    P --> C[circuits · threads cascade]
    C --> T[threads 행 삭제]
    T -->|트리거| K[LangGraph 체크포인트 3표 삭제]
    T -->|FK cascade| A[agent_threads → agent_messages · analysis_events]
    T --> R[runs → messages → approvals → quotes · approved_cases]
    U --> S[Store 사실 3칸: 코드가 삭제, 라이브러리 표라 FK 불가]
```

## 3. 보류안(P3): 이중 구조를 끝까지 합친 모양 — 지금은 하지 않는다

```mermaid
erDiagram
    projects ||--o{ threads : "대화 + 분석 상태"
    threads ||--o{ runs : "질문 실행"
    threads ||--o{ messages : "메시지(조건 · 체크포인트 칸 추가)"
    threads ||--o{ analysis_events : "운영 기록"
    threads {
        uuid id PK
        bigint project_id FK
        text target "agent_threads에서 이동"
        int version "이동"
        text status "이동"
        jsonb input_record "이동"
    }
    messages {
        bigint id PK
        text conditions "신규"
        text checkpoint_id "agent_messages에서 이동"
    }
```

`sojafit_agent.threads` · `messages`를 `public`으로 합쳐 분석 서비스에 "대화 상태" 표가 하나만 남는 모양이다. 효과는 가장 크지만 분석 서비스 전체(`memory_service.py` 약 15개 함수)와 시험 60여 개를 다시 써야 하고, 분석 입력 문자열이 조금이라도 달라지면 키 없는 데모의 기록 재생이 깨진다([`impact.md`](impact.md) 4절). 추천안(그림 1)은 이 합치기의 **전제(FK, 단일 회로 사본)**까지만 만든다.
