# 동결 직전 검사: pytest · 동결 평가셋 · 비밀값 (2026-11-16)

강사 11/16 코멘트 ④ 먼저 할 것 "동결 직전 pytest, freeze 검사, gitleaks 결과를 저장소에 남기세요"에 대한 기록이다.

| 검사 | 대상 커밋 | 결과 [실측] | 원본 |
|---|---|---|---|
| 전체 pytest(Linux 컨테이너) | `jeongun` `4c5afc1e` | **2,495 통과 · 0 실패 · 190 건너뜀**(67초). 저장소 Dockerfile로 `--no-cache` 빌드한 이미지(python 3.12.16, aarch64, cairo 포함)에 git을 설치하고 사본을 git 저장소로 만든 뒤 `uv run --locked pytest -p no:cacheprovider -rs`(11-13 실행 B와 같은 방법). 건너뜀은 전용 `TEST_DATABASE_URL` 필요 등(`-rs` 목록) | [pytest_full_linux.txt](pytest_full_linux.txt) |
| 동결 평가셋(`evals/runners/freeze.py --check`) | `jeongun` `4c5afc1e` | **동결 이후 바뀐 파일 없음**, 종료 코드 0. v1 50 · v2 70 · v3 50의 sha256이 `evals/FROZEN.json`과 같다 | [freeze_check.txt](freeze_check.txt) |

참고: 같은 커밋을 macOS 호스트에서 돌리면 2,485 통과 · 12 실패 · 188 건너뜀이다. 실패 12개는 모두 `tests/projects/test_schematic_render.py`의 SVG 시험이고 원인은 호스트에 cairo 네이티브 라이브러리가 없는 것(`no library called "cairo"`)이다. Linux 이미지에는 `libcairo2`가 있어 통과한다.
