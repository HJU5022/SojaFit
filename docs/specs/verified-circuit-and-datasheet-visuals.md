# 검증된 회로도와 데이터시트 근거

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 정본(데모 회로 원본 회로도 카탈로그, 데이터시트·패키지 외형 링크 규칙)
- 관련 문서: [verified-circuit-and-datasheet-visuals-plan.md](verified-circuit-and-datasheet-visuals-plan.md)(구현 계획, 실행 완료), [circuit-context-diagram.md](circuit-context-diagram.md), [official-datasheet-evidence.md](official-datasheet-evidence.md), [data/circuits/CIRCUITS.md](../../data/circuits/CIRCUITS.md)

## Why

대체 부품 결과만 보여 주면 사용자는 실제 회로 맥락과 판정 근거를 직접 확인하기 어렵다. 데모 회로의 공개 원본과 후보 부품의 공식 데이터시트 위치를 함께 제공하되, 개념도를 실제 설계 원본으로 오해시키거나 물리적 직접 교체를 보증해서는 안 된다.

## Goal

- 카탈로그에 등록된 데모 회로 15종 모두에서 공개 원본 회로도와 기존 연결 개념도를 구분해 표시한다.
- 선택 후보의 공식 데이터시트, 인용 페이지, 패키지 외형 페이지를 서버가 만든 정규 메타데이터로만 제공한다.
- 새 데모는 Python·TypeScript·Docker 목록을 고치지 않고 `data/circuits/catalog.json`과 `data/circuits/visuals.json` 등록으로 추가한다.
- 범위 밖: 업로드 프로젝트의 원본 회로도 생성·추정, 외부 PDF 삽입·프록시, 회로 방향·핀 재배선·납땜 방법 생성, 새 그래프·PDF 뷰어 라이브러리.

## What

- 데모 회로 15종 모두에 고정 커밋에서 확인한 원본 회로도 PNG를 제공한다.
- 업로드 프로젝트에는 원본 회로도 탭이 나타나지 않는다.
- 원본 회로도와 연결 개념도는 별도 탭이다.
- 후보 근거에는 공식 HTTPS 데이터시트 링크와 패키지 외형 페이지 링크를 표시한다.
- 패키지 결과 문구는 세 가지다. 이 표현은 직접 교체를 보증하지 않는다.

| `board_change` | 표시 문구 |
|---|---|
| `false` | 동일 패키지 가능성 |
| `true` | 기판 변경 가능성 있음 |
| 없음 | 패키지 변경 여부 확인 필요 |

## How

| 항목 | 내용 | 근거 |
|---|---|---|
| 회로 목록 정본 | `data/circuits/catalog.json`. 키는 데모 ID 15개, 값은 `name`, `connections_path`. 백엔드는 `backend/projects/catalog.py`, 더미 UI는 `frontend/vite.config.ts:13`, Docker 이미지는 `data/circuits/` 폴더 전체 복사(`Dockerfile:9`)로 읽는다 | `backend/projects/catalog.py:9,30`, `Dockerfile:9` |
| 원본 회로도 정본 | `data/circuits/visuals.json`. 항목은 `image_url`, `original_url`, `source_repo`, `source_commit`(40자리), `license`, `license_evidence_url`, `attribution`, `sha256`(배포 PNG), `source_sha256`(원본). 키 집합은 `data/circuits/catalog.json`과 정확히 같아야 한다 | `backend/projects/visuals.py:18-37,43` |
| 정적 PNG | `frontend/public/circuit-schematics/<데모 ID>.png` 15개. 로딩 시 SHA-256 일치를 검사한다. 빌드된 `frontend/dist`가 있으면 그쪽을 검사한다 | `backend/projects/visuals.py:40-58` |
| 출처 의미 | 저장소 커밋은 저장소 맥락이다. CDN 바이트의 출처 증명은 `original_url`과 `source_sha256`이다 | `backend/projects/visuals.py:18-30` |
| 카탈로그 API | `GET /api/demo-circuits`. 로그인 필요. 쿼리 `q`(ID·이름 부분 일치), `offset`(0 이상), `limit`(1~100, 기본 100). 응답 `Cache-Control: public, max-age=300`. 각 항목은 `id`, `name`, `schematic` | `backend/api/projects.py:69-80` |
| 업로드 프로젝트 | 원본 회로도 탭은 `project.source_kind === 'demo'`이고 `schematic`이 있을 때만 | `frontend/src/components/CircuitSummary.tsx:19` |
| 데이터시트 URL | `data/manifest.jsonl`의 `source_url`에서 URL-decode한 PDF 파일명을 소문자로 바꿔 정확히 일치할 때만 사용한다. 호출자가 준 URL은 출처로 받지 않는다 | `backend/rag/source_metadata.py:18-60` |
| 패키지 외형 페이지 | `data/package-outline-pages.json`(문서 1,360개)을 오프라인 도구가 Docling JSON에서 만든다. 허용된 표제와 같은 페이지에 그림이 있는 최초 페이지. 없으면 도구가 실패한다 | `backend/rag/pipeline/package_outlines.py:40-70`, 문서 수는 JSON 키 수를 직접 셈 |
| 응답 정규화 | 모델·클라이언트가 보낸 URL·외형 페이지는 버리고 서버 메타데이터로 덮어쓴다 | `backend/conversations/dto.py:79-86,249,265` |
| 링크 | 외부 PDF는 inline 삽입·프록시 없이 새 탭 링크(`target="_blank"`, `rel="noreferrer noopener"`)로 연다 | `frontend/src/components/EvidencePanel.tsx:36-37` |

## AC

- 데모 15종에서 원본 회로도, 출처, attribution과 license를 확인할 수 있다.
- 카탈로그 항목을 추가할 때 애플리케이션 코드나 Docker의 파일 목록을 수정하지 않는다.
- 카탈로그 API의 검색·범위 제한이 정상 입력과 잘못된 입력을 구분한다.
- 업로드 프로젝트에는 원본 회로도 탭이 나타나지 않는다.
- 선택 후보의 공식 데이터시트와 패키지 외형 페이지 링크가 manifest·오프라인 index에서만 생성된다.
- 알 수 없는 문서와 악성 URL 입력은 브라우저 링크가 되지 않는다.
- UI에 물리적 무수정 교체, 핀 호환, 재배선·납땜 방법을 보장하는 문구가 없다.

## 구현 상태

| 영역 | 테스트 | 상태 |
|---|---|---|
| 카탈로그·원본 회로도 검증 | `tests/projects/test_catalog.py`, `tests/projects/test_visuals.py` | 구현 |
| 카탈로그 API | `tests/api/test_projects.py` | 구현. 검색·범위 케이스 대응은 대조하지 않음 |
| 외형 페이지 index | `tests/rag/test_package_outlines.py` | 구현 |
| 안전 인용 DTO | `tests/conversations/test_dto.py` | 구현 |
| 화면 | `frontend/src/components/CircuitSchematic.test.tsx`, `frontend/src/components/D5Panels.test.tsx` | 구현. 패키지 문구 3종은 `frontend/src/components/D5Panels.test.tsx:632,644,654` |

## 한계

- 대상 Playwright 흐름과 production build 통과는 이 문서 기준일에 다시 실행하지 않았다(미확인).
- 데이터시트 파일명이 manifest에 없는 문서는 링크가 생기지 않는다.
- `visuals.json`의 `license_evidence_url` 응답 상태는 외부 호출이 필요해 확인하지 않았다.
