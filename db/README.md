# db

## 역할
- 이 폴더: Compose가 DB 컨테이너를 처음 만들 때 이름순으로 실행하는 초기화 SQL을 둡니다. 자동 실행하지 않는 SQL은 `manual/`에 둡니다.
- 넣는 것: 확장과 스키마, 스냅샷 데이터 적재, 인덱스 생성 SQL. 로컬 Compose 데모 계정은 `007_demo_accounts.sql`이 `.env`의 이메일·scrypt 해시로 만들고, 그 밖의 계정은 `python -m backend.auth`로 만듭니다. 실제 비밀번호는 저장소에 넣지 않습니다.
- 넣지 않는 것: 평가용 계정 비밀번호(강사에게 따로 제출), 원본 문서(`data/corpus/`).
- 담당: 서비스·운영 (RAG 스키마·스냅샷·인덱스 SQL은 검색·데이터)

## 실행과 주의
- 실행 SQL과 초안은 세 자리 접두사를 사용합니다. 번호는 파일 실행 순서이며 기존 문서의 논리적 Migration 1·2 명칭과는 별개입니다. `001`은 비워 둡니다. 이미 적용한 파일의 이름과 번호는 바꾸지 않습니다.
- 빈 DB 볼륨을 처음 만들 때 실행 SQL은 파일명 순서로 적용됩니다. 현재 순서는 `000_init.sql` → `002_rag_corpus.sql` → `003_auth.sql` → `005_auth_attempt_window.sql` → `006_user_roles.sql` → `007_demo_accounts.sql`입니다. 데모 모드에서 네 개의 계정 설정 변수가 모두 비어 있으면 기본 데모 계정이 생성됩니다. 네 값이 모두 유효하면 해당 계정을 사용하고, 일부만 설정하면 초기화가 실패합니다. 데모 모드가 꺼져 있고 네 값이 비어 있으면 기본 계정을 생성하지 않습니다.
- Compose 초기화는 이 폴더 바로 아래 파일만 실행하므로 `manual/`의 SQL은 자동 실행되지 않습니다. 업무 표 초안(`manual/004_create_business_tables.sql.draft`)은 코퍼스 SQL과 인증 SQL이 먼저 필요하며, 자동 실행 전 파일 순서·마이그레이션 이력 방식을 확정해야 합니다.
- 이미 초기화된 DB 볼륨에는 추가·변경한 초기화 SQL이 자동으로 적용되지 않습니다. `007_demo_accounts.sql`도 새 볼륨 생성 때만 자동 실행되며, 기존 DB에는 환경변수를 준비한 뒤 검토된 SQL을 별도로 적용합니다. 기존 DB의 구조와 적용 이력을 확인하고 별도 마이그레이션 방식을 정합니다(아래 "기존 DB 인증 스키마 적용 전 점검").
- `docker compose down -v`는 DB 볼륨의 데이터를 삭제합니다. 기존 데이터를 보존해야 하는 환경에서는 실행하지 않습니다.

## 파일
- `000_init.sql` — pgvector 확장 생성
- `002_rag_corpus.sql` — 코퍼스 문서·청크·임베딩 테이블과 관련 인덱스
- `003_auth.sql` — 사용자·인증 세션·로그인 시도 테이블
- `005_auth_attempt_window.sql` — 로그인 실패 집계 시간 컬럼 추가
- `006_user_roles.sql` — 계정 역할 추가. 기존 계정은 일반 사용자로 유지하며 관리자는 `python -m backend.auth --role admin`으로 따로 만든다
- `007_demo_accounts.sql` — 로컬 Compose용 관리자·일반 데모 계정 생성. 데모 모드 기본 계정 또는 네 환경변수로 지정한 이메일·scrypt 해시를 사용한다. `$`가 포함된 해시는 `.env`에서 작은따옴표로 감싼다. 실제 계정 비밀번호는 저장소에 두지 않는다. 새 볼륨 초기화 때 한 번 실행
- `manual/` — 자동 실행하지 않는 SQL(업무 표 초안, halfvec 수동 전환). [README.md](manual/README.md)
- `ERD.md` — 테이블의 역할과 생성 위치. SQL로 테이블을 바꾸면 같은 PR에서 고칩니다
- `table-definition.md` — 업무 테이블의 컬럼·관계·제약조건과 검토 항목

## 기존 DB 인증 스키마 적용 전 점검

1. 대상이 공유·운영 DB인지 확인하고, 현재 적용 이력과 백업·복구 경로를 담당자와 확인합니다. 비밀번호·접속 문자열은 기록하지 않습니다.
2. 읽기 전용으로 현재 스키마와 필요한 컬럼·제약을 확인합니다. 예시:

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('users', 'auth_sessions', 'auth_login_attempts');

SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('users', 'auth_sessions', 'auth_login_attempts')
ORDER BY table_name, ordinal_position;

SELECT conrelid::regclass AS table_name, conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid IN (SELECT oid FROM pg_class WHERE relnamespace = 'public'::regnamespace
  AND relname IN ('users', 'auth_sessions', 'auth_login_attempts'))
ORDER BY conrelid::regclass::text, conname;
```

3. 테이블이 모두 없는 경우, 별도 빈 테스트 DB에서 `003_auth.sql`, `005_auth_attempt_window.sql`, `006_user_roles.sql` 순서로 적용하고 로그인 테스트를 먼저 확인합니다. 이미 일부 또는 전체가 있으면 해당 정의·데이터·이력을 비교해 필요한 후속 마이그레이션을 별도로 작성합니다. `CREATE TABLE IF NOT EXISTS`만으로 기존 구조의 일치를 보장하지 않습니다.
4. 적용 경로와 이력 관리 방식은 팀 검토 후 확정합니다. 운영·공유 DB에 자동 적용하거나 볼륨을 삭제하지 않습니다.

- 이미 `auth_login_attempts`가 있으면 `window_started_at` 존재 여부와 적용 이력을 확인합니다. 컬럼이 없고 다른 구조가 인증 코드와 일치하는 경우에만 검토된 `005_auth_attempt_window.sql` 적용을 계획합니다. 존재한다면 무조건 다시 실행하지 않습니다. 기존 데이터를 지우지 않고 테스트 DB에서 먼저 확인합니다. 애플리케이션 갱신 전 DB 마이그레이션이 선행돼야 합니다.
- `006_user_roles.sql`도 기존 `users.role` 유무와 이력을 확인한 뒤 한 번만 적용합니다. 기존 계정은 `user`로 유지합니다. 새 API 코드보다 먼저 반영해야 합니다.
- `007_demo_accounts.sql`은 새 Compose 볼륨에서만 자동 실행됩니다. 기존 DB에 적용할 경우 대상 계정 이메일의 중복과 역할을 확인하고 테스트 DB에서 먼저 검증합니다. 시드 SQL은 이미 있는 계정의 비밀번호나 역할을 덮어쓰지 않습니다.
