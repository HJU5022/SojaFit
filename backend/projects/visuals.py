"""배포 회로도와 원본 출처 정본을 검증한다. 외부 다운로드는 하지 않는다."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.projects.catalog import catalog_by_id

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "data/circuits/visuals.json"
PUBLIC_ROOT = ROOT / "frontend/public"
DIST_ROOT = ROOT / "frontend/dist"
VERIFIED_DEMOS = frozenset(catalog_by_id())


class DemoVisualRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    image_url: str
    original_url: str = Field(pattern=r"^https://[^\s/]+/\S+$")
    source_repo: str = Field(pattern=r"^https://[^\s/]+/\S+$")
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    license: str
    license_evidence_url: str = Field(pattern=r"^https://[^\s/]+/\S+$")
    attribution: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("license", "attribution")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("회로도 라이선스와 저작자 표기는 비워 둘 수 없습니다.")
        return value


@lru_cache(maxsize=1)
def load_demo_visuals() -> dict[str, DemoVisualRecord]:
    """카탈로그에 등록된 모든 회로의 배포 PNG를 검사한다. 미빌드 개발 환경에서만 public을 쓴다."""
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or set(catalog) != VERIFIED_DEMOS:
        raise ValueError("회로도 카탈로그는 등록된 회로와 정확히 일치해야 합니다.")
    records = {}
    asset_root = DIST_ROOT if DIST_ROOT.is_dir() else PUBLIC_ROOT
    for demo_id, raw in catalog.items():
        item = DemoVisualRecord.model_validate(raw)
        if item.image_url != f"/circuit-schematics/{demo_id}.png":
            raise ValueError(f"잘못된 회로도 자산 경로: {demo_id}")
        asset = asset_root / item.image_url.lstrip("/")
        if not asset.is_file():
            raise ValueError(f"회로도 자산 누락: {demo_id}")
        if hashlib.sha256(asset.read_bytes()).hexdigest() != item.sha256:
            raise ValueError(f"회로도 자산 SHA-256 불일치: {demo_id}")
        records[demo_id] = item
    return records
