# 시장 근거 원자료 색인

- 상태: 현행
- 기준일: 2026-10-29 (수집 기준일. 각 파일의 `generated`, `checked_on`, 집계 제목에 적힌 날짜)
- 정본 여부: 정본(이 폴더 파일의 목록과 sha256)
- 관련 문서: [docs/TOPIC.md](../../TOPIC.md)(각주 [1]~[4]), [market-user-journey.md](../market-user-journey.md), [job-postings-summary.md](job-postings-summary.md)

## 1. 범위

`docs/TOPIC.md` 각주와 `market-user-journey.md`가 가리키는 조사 파일 중 저장소에 둘 수 있는 9개. 모두 조장 로컬 조사 폴더의 원본과 바이트가 같은 복사본이다(복사 시 `cmp` 일치 확인. 원본은 저장소에 없어 지금은 다시 확인할 수 없다). 파생·재작성 파일은 없다.

| 항목 | 값 |
|---|---|
| 이름 변경 | `집계.md`는 레포 구조 시험(한 폴더 한 종류)에 맞춰 `job-postings-summary.md`로 바꾸고 `job-postings/` 밖에 뒀다. 폴더 `jobs2/`는 `job-postings/`로, `corpus2/`의 두 파일은 `corpus/`로 합쳤다. 파일 내용은 같아 sha256이 그대로다 |
| 남은 옛 이름 | `job-postings/merged.json`의 `_file` 값에 `jobs2/`가 남아 있다 |
| 확인 방법 | 저장소 루트에서 `shasum -a 256 docs/research/evidence/<경로>`로 3절의 해시와 대조한다. 9개 모두 일치한다 [실측] |

## 2. 필드 정의

| 파일 | 필드 |
|---|---|
| `job-postings/*.json`의 공고 한 행 | `company`, `title`, `url`, `source`, `career`, `newgrad_ok`, `status`, `llm_rag_agent`, `ai_role`, `segment`, `deadline`, `notes`. `merged.json`은 `detail_opened`, `_file`이 더 있다 |
| `netlist/manifest_diodes.json` | `est_role`(규칙 추정), `reviewed_role`(에이전트가 넷 이름으로 붙인 임시 정답. 사람이 확정한 값이 아니다. 파일의 `note`) |

## 3. 목록

| 각주 | 저장소 경로 | sha256 | 크기(바이트) | 무엇을 보이나 |
|---|---|---|---|---|
| [1] | `corpus/manifest_diode.json` | `109aa6da24f22e0f0ab58025a2d1c50168066a226c4777cadeca139193c9bd89` | 45,192 | 다이오드 데이터시트 41건의 쪽수·조각 수 실측(고유 조각 627개, 문서당 평균 15.3개) |
| [1] | `corpus/manifest_open_extra.json` | `3af4e85fd5161cd8a4e4e80f9709524d6e2f5b87ccc59f260fb7d922d8bab2da` | 19,226 | KiCad 문서 등 공개 문서의 조각 수 실측 |
| [1] | `corpus/manifest_open_docs.json` | `2daedb06563b9e3f980ca06b1285b7f8ec8d2b81d9c1a50137da820d85b01086` | 1,247,343 | 공개 문서 출처별 조각 수 실측 |
| [2] | `job-postings-summary.md` (원본 이름 `evidence/jobs2/집계.md`) | `dabf563c14b3eb33cbbd5ea137aefeaa96d68dec103ecb99f1a6d7a398e6aa4e` | 2,229 | 제조 산업 AI 공고 237건 집계(열림 216 · AI 직무 170 · LLM 명시 77 · 신입 가능 44) |
| [2] | `job-postings/merged.json` | `06d396b0f9bb742053d0b8f029f5c9928ad8619d14eb886592e315fc156d66d3` | 142,236 | 중복 제거한 공고 237건의 개별 행(회사·직무명·URL·출처·경력·신입 가능·상태·LLM 명시 여부) |
| [2] | `job-postings/wanted_jumpit.json` | `06bc077894de64b25b035d4cd3c2edd3ba7c92d04a12f59c09a1cb6cfba3e8b5` | 45,810 | 원티드·점핏 수집분 89건 |
| [2] | `job-postings/saramin_jobkorea.json` | `e3923c6669a04ae7a2ae3105eca60eca0caed5aa53175cc09b572170f1e64579` | 79,231 | 사람인·잡코리아 수집분 136건 |
| [2] | `job-postings/company_pages.json` | `4870e92557e0e13bd8d8520e26c849aa5a294b6285eb42beafeacdd2cf6eb247` | 14,367 | 회사 채용 페이지 수집분 24건 |
| [4] | `netlist/manifest_diodes.json` | `9a1af6b84b8dd20e794059c39ba02febb623fd678a7a3f0563157ccdab1c115e` | 495,239 | 공개 KiCad 프로젝트 151개(파일 216개)의 다이오드 554개(중복 제외)와 역할 후보 |

각주 [3]의 근거 파일(`후보 G 시장 포화 비교.md`, `1차관문-회로역할대체.md`)은 저장소에 없다.

## 4. 한계

- 집계의 분류, AI 직무, LLM 명시 판단은 수집 에이전트가 제목과 본문으로 한 추정이다([job-postings-summary.md](job-postings-summary.md) 방법 절).
- 각주 [3]의 근거 파일이 없다. 조장 PC의 절대 경로(사용자 이름 포함)가 들어 있어 옮기지 않았다.
- `job-postings-summary.md`가 링크한 이전 목록(`../jobs/postings.json`)과 수집 로그(`*_searchlog.json`, `company_pages_log.json`)는 저장소에 없다.
- `corpus/`의 측정 스크립트(`measure_*.py`, `parse_kicad_diodes.py`)와 회로 본문은 저장소에 없다.
- `netlist/manifest_diodes.json`의 저장소 이름·URL은 공개 GitHub 저장소(MIT, CC BY-SA)의 것이다.

## 5. 파일
- `corpus/` — 공개 문서·다이오드 데이터시트 조각 수 실측 3개(`manifest_open_docs.json`, `manifest_diode.json`, `manifest_open_extra.json`)
- `job-postings/` — 공고 수집 원자료 4개(`merged.json`, `wanted_jumpit.json`, `saramin_jobkorea.json`, `company_pages.json`)
- `job-postings-summary.md` — 공고 237건 집계(`job-postings/`에 마크다운을 섞을 수 없어 밖에 둠)
- `netlist/` — 공개 KiCad 프로젝트 다이오드 목록 `manifest_diodes.json`
