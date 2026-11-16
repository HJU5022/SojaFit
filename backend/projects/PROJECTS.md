# projects

## 역할
- 이 폴더: 사용자 소유 프로젝트·정규화 회로 저장소와 공개 DTO, 데모 회로 catalog 검증, 외부 공개 회로도 검색·변환.
- 넣는 것: 소유 사용자 조건이 붙은 프로젝트 SQL(`repository.py`), 단일 catalog(`data/circuits/catalog.json`)의 데모 복제와 회로도 출처 검증, 제한된 KiCad export 정규화(`netlist.py`), 외부 회로도의 검색 후보 정제·원본 확인·PNG 변환.
- 넣지 않는 것: 서비스 HTTP 라우트와 multipart 수신(`backend/api/`), 원본 넷리스트·가격 저장, 분석 실행(`backend/multi_agent/`). 예외: `schematic.py`의 `app`은 KiCad 변환 서버(`/health`, `/render`)로, `Dockerfile`의 `renderer` 단계가 따로 띄운다.
- 담당: 서비스·운영

저장소는 `auth.connection()`과 `db/020_service_baseline.sql`·`db/031_circuit_versions.sql`·`db/035_circuit_schematics.sql`의 표를 쓴다. 모든 조회·변경·삭제에 `user_id` 조건이 붙고 관리자 예외는 없다. 빈 프로젝트는 v0, 데모 복제·처음 업로드는 v1이다. 기존 프로젝트에 업로드하면 프로젝트 잠금 아래 새 불변 버전과 새 대화를 한 트랜잭션으로 저장한다. 회로가 없던 프로젝트에 그 프로젝트의 버전 0 대화 `thread_id`를 주면 새 대화 대신 그 대화를 돌려주고, 그 대화는 처음 올린 회로를 읽는다(SPEC 8.9). `circuits`는 최신 버전이고 `project_circuit_versions`는 과거 회로를 보존한다. 서비스의 프로젝트 삭제는 `backend/api/projects.py`의 `delete_owned_with_checkpoints`가 같은 UUID의 분석 기록(체크포인트 · thread)까지 지우고 나머지는 FK cascade를 쓴다. `ProjectRepository.delete_owned`는 시험만 부른다. 업로드 정규화의 크기·깊이·개수 상한과 파서 버전은 `netlist.py` 상수(`MAX_BYTES`, `MAX_DEPTH`, `MAX_TOKENS`, `MAX_COMPONENTS`, `MAX_NETS`, `PARSER_VERSION`)가 정본이다. 데모 회로의 출처와 라이선스는 [CIRCUITS.md](../../data/circuits/CIRCUITS.md)를 따른다.

외부 다이오드 회로 검색은 공식·공개 웹 후보를 먼저 검증하고, 확인된 자료가 없으면 BOM 색인과 독립 GitHub 검색 경로로 저장소 후보를 최대 24개 검증한다. discovery는 최대 128파일·파일당 4MiB·총 25MiB까지 현대 KiCad 파일을 먼저 읽는다. 렌더링은 검증한 선택 계층만 고정 commit에서 직접 다운로드하며 파일당 10MiB·총 25MiB·최대 20시트로 제한한다. 검색과 무관한 다른 프로젝트의 손상 파일을 격리하되 선택한 계층의 누락·순환은 거부한다. 품번은 실제 배치 심벌에서 확인하고, 구형 KiCad의 instance 값은 배치 UUID·참조번호가 일치할 때만 사용한다. 사용자 정의 다이오드는 설명과 양극/음극 핀 구조를 함께 검사한다. 저장소의 여러 완전한 회로가 일치하면 서로 섞지 않고 고정 commit·root별 선택 URL을 제공한다. 전체 시트 PNG 변환까지 통과한 후보와 이미지를 15분 캐시하며, 선택 실패를 다른 회로로 대체하지 않는다. 일부 저장소의 검사나 원본 렌더링이 한도·외부 오류로 실패하면 오류와 재시도 정보를 캐시에 보존한다. 정상 후보 선택은 유지하되 Retry-After 경과 후(일반 외부 오류는 60초 후) 같은 검색의 후보·검증·선택 캐시를 비우고 재검사한다. 후보 선택으로 이 재검사 시점을 연장하지 않는다.

TSC 공식 제품 자료는 제한된 참고 회로 예외로 다룬다. 공식 제품 필터 API `https://services.taiwansemi.com/api/products_v2`에서 검색 품번의 `name`, `status`, `datasheet`를 확인한 뒤 해당 공식 PDF를 받아 응용 회로 페이지와 원본 SHA-256을 검증한다. 검색어는 API 발견 단계에서 품번 앞부분(keyword prefix)으로 사용할 수 있지만, `TSC` 없는 bare 품번은 `TS` 뒤 4자리 이상 숫자로 시작하거나 `TSCR` 3자리 이상·`TSL` 숫자·`TQL` 3자리 이상 영숫자 계열이고 전체 품번 패턴이 일치할 때만 `tsc <품번>`으로 정규화한다. 일반 `SS33`·`1N4148`·`Raspberry Pi` 검색은 기존 경로를 사용하며, 이 정규화 경로는 기존 GitHub 제한·후보 캐시와 분리한다. API의 실제 `name`과 PDF 본문에는 요청 품번의 정확한 표기가 있어야 하며 변형을 추정하지 않는다. API의 `records`가 비어 있을 때는 `services.taiwansemi.com/storage/resources/datasheet/` 공식 원문 전용 Exa 검색을 한 번 보완할 수 있으며 GitHub 호출은 하지 않는다. 공식 API에 없는 품번 변형을 같은 제품으로 추정하지 않고, H 접미사 등은 실제 `name`·PDF 본문에 확인된 표기 그대로 둔다. 문서 전체의 공식 브랜드·정확 품번과 선택 페이지의 `Typical Application Circuit` 제목·vector wire 또는 공식 raster 연결선(밝은 배경, 얇은 직교선, 최소 8개 선과 2개 T분기)을 모두 확인한다. 이 경로는 TSC 제품 확인과 데이터시트 안의 응용 회로 표시만 허용하며 공개 완성 보드 회로도나 임의의 사용자 URL을 대체하지 않는다. 기존 HTTPS/SSRF, PDF 형식·크기·해시, 캐시와 공급자 한도를 유지하고, 기존 내부 검색 경로·manifest/choices/API 계약도 유지한다. 제조사 전체의 데이터시트 허용으로 일반화하지 않으며 주요 `SPEC.md` 변경은 조장 검토로 남긴다.

TI·STMicroelectronics·Analog Devices·onsemi·Infineon·Vishay를 명시한 검색은 해당 공식 호스트의 공개 회로도·데이터시트 응용 회로·Application Note를 참고 자료로 검증한다. 명시 제조사 검색은 일반 웹·GitHub로 대체하지 않고, 공식 호스트·요청 모델/문서 식별자·실제 부품과 배선을 함께 확인한다. 원문 PDF 검사 최대200쪽과 반환 최대20시트를 구분하며 20MiB·worker·PNG 제한은 유지한다. 정상 RF 다이오드 응용 문서는 실제 품번·사용 근거가 있어야 하며 동명 무전기·다른 품번·블록도·핀배치·사진은 제외한다. TSC 제품 API와 기존 원본 전체 연결 일치 경계는 그대로 유지한다. 공식 출처 확인을 이용·재배포 허가로 표시하지 않는다.

2등급 제조사는 영어 공식 자료가 확인된 경우에만 등록한다. 현재 6개 반도체 제조사와 TSC는 유지하며 번역본이 함께 있다는 이유로 제외하지 않는다. 반도체 검색은 영어를 명시하고 공식 URL의 비영어 경로·언어 쿼리를 거절한다. 확인 가능한 TI 품번 symlink만 영어 경로로 정규화하며 다른 번역 문서 ID는 추정하지 않는다. 반도체·TSC PDF는 소개 3쪽과 선택 회로 페이지의 영어 텍스트를 보수적으로 확인한다. 설명문 없는 영어 CAD 시트는 project/sheet 필드·부품 참조로 구분하며, 영어 제목만 붙은 비영어 본문은 승인하지 않는다. 출처·해시·서명은 실제 영어 원문 기준이며 API DTO·UI·RAG 행 검색 등급 계약은 바꾸지 않는다.

제조사 없는 품번은 이름 접두어로 회사를 추정하지 않고 반도체6공식호스트에서 함께 검색한다. 검색 메타데이터가 아닌 PDF 본문에서 정확 품번을 확인한다. 제조사별 첫 후보를 우선하며 bare 모호성 검사는 최대6후보, 정상 응답 표시는 기존최대5후보다. 둘 이상의 제조사가 검사·PNG 변환까지 통과하면 `ambiguous_manufacturer`로 처리하고 선택 URL·캐시로 첫 제조사를 강제하지 않는다. 다른 제조사의 조회 오류도 단일 제조사 확인으로 취급하지 않는다. 공식 후보가 전혀 없는 품번의 기존 공개/커뮤니티 보완은 유지한다. API 필수 인자나 UI 변경 없이 기존 오류 영역과 입력칸을 사용한다.

6개 공식 반도체 PDF는 첫 검색 요청의 검사→변환 사이에 통과한 바이트·쪽수만 ContextVar로 전달한다. URL·모델·제조사·원문 해시·시트 수를 대조하고 해시를 다시 확인하며, 같은 내용 검사를 반복하지 않는다. 연속 공식 PDF 후보는 최대2개씩 검사하고 프로세스 공통 동시 검사 상한도2개다. 준비 원문은 요청마다 최대2개·각20MiB 이내로 잠금 보호하며 배치/요청 종료·예외 때 해제한다. 두 검사 결과는 원래 후보 순서로 처리하고 렌더·요청 전체 재시도1회·모호성 집계는 주 스레드에 유지한다. DTO·토큰·기존 캐시에 원문을 넣지 않고 별도 이미지 조회나 임시 자료 미일치는 기존 재검증 경로다. 익명 source_id별 횟수·단계 시간과 실제 검사 중첩 구간·최대 동시 수를 기록한다. TSC·공개 웹·KiCad·원본 연결 경로, 조기 종료·검색 변경·요청 간 PDF 캐시는 추가 변경하지 않는다.

GitHub 라이선스 metadata의 deprecated GPL 식별자는 canonical SPDX 표기로 정규화한다. `NOASSERTION`은 일괄 허용하지 않으며, 고정 원문의 구조화된 CERN-OHL 고지와 README의 명시적인 전체 hardware 적용 범위가 일치하고 추가 제한이 없는 경우에만 선언된 라이선스와 원문 근거 URL을 반환한다. 제조사 공식 확인과 커뮤니티 라이선스 선언은 별개의 정보다. GitHub API의 정상 JSON 응답은 인증 설정별·URL별로 15분, 최대 128건·16MiB 범위에서 재사용한다.

상위 계층의 다른 시트를 검사하지 못해도 검색 부품을 포함한 하위 계층 자체가 완전하면 그 하위 원문을 별도 후보로 제공한다. 완전한 상위 계층을 제공할 수 있으면 포함된 하위 후보는 중복 노출하지 않는다. 선택된 하위 계층의 누락·순환 검사는 생략하지 않는다.

## 검색 · 원본 제공 계약

검색어는 발견용 키워드로 취급하며 3자 이상 단어/품번의 앞부분도 대조한다. 숫자 부품 키워드는 실제 배치 정보에서 확인하고 전압/단위·출처·자료 유형·업로드 전체 연결 검증은 유지한다. 품번 없는 다이오드 용도 검색은 기존 GitHub 경로와 동일 상한을 사용한다. manifest의 검증된 choices를 먼저 표시하고 도면은 사용자가 선택한 뒤 표시하며, 후보 제목은 파일 식별정보를 포함한다.

프로젝트 원본은 소유 회로 버전의 전체 연결과 일치한 native EDA만 제공한다. 원격 렌더러는 공개 후보의 실제 export 연결과 PNG를 반환하며, API가 업로드 연결과 대조한다. 업로드 연결은 외부 검색·렌더러에 보내지 않는다. 공개 PDF·이미지의 기존 원본/게시 내용 검사는 참고 검색에만 사용한다. 다이오드 참고 모드를 골라도 프로젝트 원본의 토큰·회로별 캐시·동일성 관문을 우회할 수 없다.

- 생성(`create_empty/create_demo/create_upload`)은 계정 행 잠금 아래 이름/최신 원본 해시 중복을 확인한다. 기본 동작은 DuplicateProject와 소유 후보 최대5개이며 allow_duplicate=True만 별도 새 프로젝트를 허용한다. 원본과 해시는 공개하지 않고 이름 변경·기존 프로젝트의 버전 업로드는 이 생성 검사 대상이 아니다.

## 파일

| 파일 | 하는 일 |
|---|---|
| `PROJECTS.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `catalog.py` | `catalog.json`의 안전한 ID·이름·저장소 내부 연결 경로를 검증하고 immutable catalog 제공(`load_catalog`, `catalog_by_id`) |
| `models.py` | 목록 메타데이터 `ProjectSummary`와 정규화 연결 정보를 포함한 상세 `Project` DTO |
| `netlist.py` | `normalize_netlist(bytes)`: KiCad export에서 연결 정보(parts/nets)만 제한된 메모리로 읽고 SHA-256과 함께 `NormalizedCircuit`으로 반환. `circuit_fingerprint`는 참조를 보존한 캐시/서명 식별, `same_circuit`는 확정 net·핀 역색인으로 후보를 좁히고 끝 숫자가 바뀐 부품의 전체 핀 연결 일대일 대응을 제한된 탐색으로 증명. 원본·경로·파일 핸들은 남기지 않음 |
| `repository.py` | `ProjectRepository`: `create_empty`, `create_demo`, `create_upload`, `import_netlist`(새 버전·대화 원자 생성, 회로 없는 대화면 그 대화 유지. 두 업로드는 올린 회로도 원문을 같은 트랜잭션에서 그 버전에 저장, #52), `uploaded_schematic`(소유자 조건으로 회로도 원문), `circuit_connections`(소유자 조건으로 그 회로 버전의 연결, 부품 점검표 #68), `list_owned`, `get_owned`(선택적 대화 버전), `rename_owned`, `delete_owned` |
| `visuals.py` | `load_demo_visuals()`가 데모 catalog의 회로도 출처 정본(HTTPS, commit, PNG 경로와 배포 PNG의 SHA-256)를 검증하고 원본 hash(`source_sha256`)는 형식만 검사. 누락·추가 ID나 손상 자산은 예외. 외부 다운로드 없음 |
| `external_circuit_search.py` | Exa 공개 웹 결과에서 회로도 이름과 파일을 확인하고 제조사·비공식 출처 후보를 정제. GitHub 저장소 후보 검색과 단일 버튼의 TSC/다이오드/공개 보드/원본 문맥 구분도 담당 |
| `external_schematic.py` | 공개 원본 후보를 검증·변환·메모리 캐시하고 서명 token으로 시트 조회. 같은 검색의 다른 후보 선택을 검증. 올린 회로도 그림도 같은 캐시(원문 해시 키)에 두고 없으면 다시 그림(#52) |
| `schematic_dialogue.py` | 검증된 후보의 공개 정보로 LLM 소개를 조립. 후보 ID·사실값·질문 모드를 검사하며 검색·원본 선택은 하지 않음 |
| `schematic.py` | 제한된 KiCad CLI PDF·netlist export와 별도 renderer HTTP 경계. 프로젝트 원본은 반환된 실제 후보 연결을 API에서 전체 대조. 올린 회로도는 `export_uploaded_kicad` → `/render {schematic}`이 (넷리스트, PNG 한 장)을 돌려줌(#52) |
| `schematic_discovery.py` | GitHub tree에서 EDA 원본과 연결된 전체 회로도 자산 찾기 |
| `schematic_render.py` | 공개 PDF/SVG/PNG의 해시·회로도 페이지를 확인하고 제한된 크기와 해상도의 PNG로 렌더링. 올린 회로도 한 장의 사전 검사(`uploaded_schematic_text`: `(kicad_sch ...)` · 내장 라이브러리 · 하위 시트 없음)와 렌더러 쪽 변환(`render_uploaded_schematic`, #52) |
| `schematic_source.py` | 검증된 외부 회로도 source DTO·서비스 오류와 호스트/인증별 제한 해제 시각. 제한 중 새 다운로드를 차단하며 최대128건의 프로세스 메모리만 사용 |
