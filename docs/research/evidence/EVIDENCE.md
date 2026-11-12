# 시장 근거 원자료 (docs/TOPIC.md 각주 [1]~[4])

- 목적: `docs/TOPIC.md` 각주와 `docs/research/market-user-journey.md`가 가리키는 조사 파일 중 저장소에 옮겨도 되는 것을 둔다. 원본은 조장의 로컬 조사 폴더에 있었고 2026-11-12에 옮겼다.
- 수집 기준일: 모두 2026-10-29(각 파일의 `generated`·`checked_on`·집계 제목에 적힌 날짜).
- 옮긴 방식: 아래 9개 파일은 원본과 바이트가 같은 복사본이다(`cmp` 일치). `집계.md`만 레포 구조 시험(한 폴더 한 종류)에 맞춰 이름을 `jobs2-summary.md`로 바꾸고 `jobs2/` 밖에 뒀고, 내용은 같다. 고치거나 다시 만든 파생 파일은 없다.
- 확인: 저장소 루트에서 `shasum -a 256 docs/research/evidence/<경로>`로 아래 해시와 대조한다.

| 각주 | 저장소 경로 | sha256 | 크기(바이트) | 무엇을 보이나 |
|---|---|---|---|---|
| [1] | `corpus2/manifest_diode.json` | `109aa6da24f22e0f0ab58025a2d1c50168066a226c4777cadeca139193c9bd89` | 45,192 | 다이오드 데이터시트 41건의 쪽수·조각 수 실측(고유 조각 627개, 문서당 평균 15.3개) |
| [1] | `corpus2/manifest_open_extra.json` | `3af4e85fd5161cd8a4e4e80f9709524d6e2f5b87ccc59f260fb7d922d8bab2da` | 19,226 | KiCad 문서 등 공개 문서의 조각 수 실측 |
| [1] | `corpus/manifest_open_docs.json` | `2daedb06563b9e3f980ca06b1285b7f8ec8d2b81d9c1a50137da820d85b01086` | 1,247,343 | 공개 문서 출처별 조각 수 실측 |
| [2] | `jobs2-summary.md` (원본 이름 `evidence/jobs2/집계.md`) | `dabf563c14b3eb33cbbd5ea137aefeaa96d68dec103ecb99f1a6d7a398e6aa4e` | 2,229 | 제조 산업 AI 공고 237건 집계(열림 216 · AI 직무 170 · LLM 명시 77 · 신입 가능 44) |
| [2] | `jobs2/merged.json` | `06d396b0f9bb742053d0b8f029f5c9928ad8619d14eb886592e315fc156d66d3` | 142,236 | 중복 제거한 공고 237건의 개별 행(회사·직무명·URL·출처·경력·신입 가능·상태·LLM 명시 여부) |
| [2] | `jobs2/wanted_jumpit.json` | `06bc077894de64b25b035d4cd3c2edd3ba7c92d04a12f59c09a1cb6cfba3e8b5` | 45,810 | 원티드·점핏 수집분 89건 |
| [2] | `jobs2/saramin_jobkorea.json` | `e3923c6669a04ae7a2ae3105eca60eca0caed5aa53175cc09b572170f1e64579` | 79,231 | 사람인·잡코리아 수집분 136건 |
| [2] | `jobs2/company_pages.json` | `4870e92557e0e13bd8d8520e26c849aa5a294b6285eb42beafeacdd2cf6eb247` | 14,367 | 회사 채용 페이지 수집분 24건 |
| [4] | `netlist/manifest_diodes.json` | `9a1af6b84b8dd20e794059c39ba02febb623fd678a7a3f0563157ccdab1c115e` | 495,239 | 공개 KiCad 프로젝트 151개(파일 216개)의 다이오드 554개(중복 제외)와 역할 후보 |

## 각주 [3]은 옮기지 않았다

`후보 G 시장 포화 비교.md`와 `1차관문-회로역할대체.md`에 조장 PC의 절대 경로(사용자 이름 포함)가 들어 있어 그대로 옮기지 않았다. 각주 [3]의 근거 파일은 이 저장소에 아직 없다.

## 읽는 법과 주의

- `jobs2/*.json`의 공고 한 행은 `company`·`title`·`url`·`source`·`career`·`newgrad_ok`·`status`·`llm_rag_agent`·`ai_role`·`segment`·`deadline`·`notes`를 가진다. 공고별 URL과 수집 사이트가 있어 `merged.json`이 공고 개별 행의 열람 자료다. 집계의 분류·AI 직무·LLM 명시 판단은 수집 에이전트가 제목·본문으로 한 추정이다(`jobs2-summary.md` 방법 절).
- `jobs2-summary.md`가 링크한 이전 목록(`../jobs/postings.json`)과 수집 로그(`*_searchlog.json`, `company_pages_log.json`)는 옮기지 않았다.
- `netlist/manifest_diodes.json`의 `reviewed_role`은 에이전트가 넷 이름으로 붙인 임시 정답이며 사람이 확정한 값이 아니다(파일의 `note`). 저장소 이름·URL은 공개 GitHub 저장소(MIT·CC BY-SA)의 것이다.
- `corpus*/`의 측정 스크립트(`measure_*.py`, `parse_kicad_diodes.py`)와 회로 본문은 옮기지 않았다.
