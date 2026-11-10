# db/migrations

## 역할
- 이 폴더: **이미 서비스 표가 있는 DB(운영)** 를 재설계 구조로 옮기는 SQL을 둡니다. 새 DB는 이 폴더를 쓰지 않고 `db/020_service_baseline.sql`로 한 번에 만듭니다. Postgres 이미지는 `db/` 바로 아래만 실행하므로 여기 SQL은 자동 실행되지 않습니다.
- 넣는 것: 운영 이전 단계별 SQL(expand → 새 코드 배포 → contract), 선택 단계, 되돌리기. 단계마다 파일 끝에서 이력 표 `public.app_migrations`에 한 줄을 남깁니다([결정] D6: Supabase의 `supabase_migrations`를 이어 쓰지 않음).
- 넣지 않는 것: 새 DB 초기화 SQL(`db/`), 설계 설명(`db/redesign/`).
- 담당: 서비스·운영

## 순서 (운영, 정운이 백업 뒤 직접 실행)
1. `migrate_prod_1_expand.sql` — 옛 코드가 돌고 있어도 안전한 "더하기"만(새 칸 · 검사 · 인덱스 · FK · 이력 표). 머리에 `pg_dump` 백업 명령.
2. P1 새 코드 배포(0% → 점검 → 100%) → 스모크.
3. `migrate_prod_2_contract_p1.sql` — 되돌릴 수 없는 삭제(스냅샷 복사본 · `display_name`).
4. P2 새 코드 배포 → `migrate_prod_3_contract_p2.sql`. 선택: `migrate_prod_2b_optional_drop_dead_auth.sql`(구글 승인 대기 표 삭제, 코드 제거 배포 뒤에만).
5. 되돌리기: `migrate_prod_4_rollback.sql`을 **적용의 반대 순서**(B2b → B2 → B1 → A)로 한 절씩. contract 뒤에는 **코드보다 DB를 먼저** 되돌린다(옛 코드가 지운 칸을 읽는다). B1 끝의 셸 단계(`db/legacy/`의 옛 검사 · 청소 함수 재생성 + `REVOKE`)도 실행한다. 다시 만든 표는 RLS ON, 함수는 PUBLIC 실행 권한 없음으로 돌아온다.
- 검증: `scripts/db/verify_chain/verify_chain.sh`가 일회용 Postgres 16 · 17에서 "옛 구조 + 이 SQL들 = 새 기준선", "되돌리기 뒤 = 처음 구조(RLS · 함수 권한 포함)"를 확인한다. 운영 DB에는 실행한 적이 없다.

## 파일
- `migrate_prod_1_expand.sql` — 1단계 expand
- `migrate_prod_2_contract_p1.sql` — 2단계 contract P1(승인 칸 NOT NULL, 스냅샷 복사본 · 미사용 칸 제거, 단순 검사)
- `migrate_prod_2b_optional_drop_dead_auth.sql` — 선택 2b(`auth_google_pending` 삭제)
- `migrate_prod_3_contract_p2.sql` — 3단계 contract P2(분석 회로 사본 · 죽은 승인 표 제거, 삭제 CASCADE, 체크포인트 삭제 트리거, 청소 함수 교체)
- `migrate_prod_4_rollback.sql` — 되돌리기(B2b · B2 · B1 · A 절)
- `MIGRATIONS.md` — 이 문서
