"""동결한 평가셋이 바뀌지 않았는지 지킨다.

- 역할: evals/FROZEN.json에 기록된 파일의 해시가 같아야 하고, 다르면 이 테스트가 PR을 막는다. 정답을 바꿔 점수를 맞추면 측정이 아니라 맞추기가 된다.
- 하지 않는 일: 평가셋 내용의 옳고 그름이나 건수 구성은 판단하지 않는다. FROZEN.json이 없으면 검사하지 않고 통과한다.
- 출처: ADR 0003(평가셋 v1 동결), AGENTS.md 지킬 것 1, evals/dataset-guide.md "동결" 절
"""
import hashlib
import json
from pathlib import Path

import pytest

from evals.run_graph import select_items

EVALS = Path(__file__).resolve().parent.parent / "evals"


def test_frozen_files_unchanged():
    """FROZEN.json에 적힌 모든 파일의 현재 sha256이 동결 당시 값과 같은지 확인한다."""
    frozen = EVALS / "FROZEN.json"
    if not frozen.exists():
        return  # FROZEN.json이 없으면 검사할 대상이 없다 (v1은 2026-11-02에 동결)
    for name, meta in json.loads(frozen.read_text(encoding="utf-8")).items():
        actual = hashlib.sha256((EVALS / name).read_bytes()).hexdigest()
        assert actual == meta["sha256"], f"{name}: 동결 후 바뀌었습니다"


def test_select_items_rejects_unknown_id():
    """없는 문항 id를 주면 조용히 빼지 않고 멈추는지(유료 실행이 일부만 돌고 정상처럼 보이는 일 방지), id 없이 부르면 전부 돌려주는지 확인한다."""
    items = [{"id": "a"}, {"id": "b"}]
    assert select_items(items, ["b"]) == [{"id": "b"}]
    assert select_items(items, []) == items
    with pytest.raises(SystemExit):
        select_items(items, ["a", "zz"])
