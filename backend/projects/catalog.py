"""검증된 회로 카탈로그의 단일 데이터 경계."""
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "data/circuits/catalog.json"
SAFE_ID = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("회로 카탈로그에 중복된 id 또는 키가 있습니다.")
        result[key] = value
    return result


@dataclass(frozen=True)
class CatalogCircuit:
    id: str
    name: str
    connections_path: Path


@lru_cache(maxsize=1)
def load_catalog() -> tuple[CatalogCircuit, ...]:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(raw, dict) or not raw:
        raise ValueError("회로 카탈로그는 비어 있지 않은 객체여야 합니다.")
    result: list[CatalogCircuit] = []
    seen: set[str] = set()
    root = ROOT.resolve()
    for circuit_id, item in raw.items():
        if not isinstance(item, dict) or set(item) != {"name", "connections_path"}:
            raise ValueError("회로 카탈로그 항목 형식이 올바르지 않습니다.")
        name, relative = item["name"], item["connections_path"]
        if not isinstance(circuit_id, str) or not SAFE_ID.fullmatch(circuit_id) or circuit_id in seen:
            raise ValueError("회로 카탈로그에 중복되거나 비어 있는 id가 있습니다.")
        if not isinstance(name, str) or not name.strip() or not isinstance(relative, str):
            raise ValueError("회로 카탈로그 이름 또는 경로가 올바르지 않습니다.")
        path = (ROOT / relative).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError(f"회로 연결 경로가 올바르지 않습니다: {relative}")
        seen.add(circuit_id)
        result.append(CatalogCircuit(circuit_id, name.strip(), path))
    return tuple(result)


def catalog_by_id() -> dict[str, CatalogCircuit]:
    return {item.id: item for item in load_catalog()}
