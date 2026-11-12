"""등록된 데모 15종의 provenance와 배포 자산 무결성을 검사한다."""
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
APPROVED = {
    "breadboard_supply", "mosfet_driver", "attiny85_dev",
    "franzininho_diy", "pro_micro", "attiny85_time_switch",
    "fc_rom_vomitter", "attiny2313a_thermostat", "tiny85_fan_control",
    "ug56_pwm_controller", "car_radio_acc_delay", "overengineered_psu",
    "tinydimmer", "hrem", "zr7_taillight",
}
SAMPLE = "mosfet_driver"


def test_visual_catalog_matches_approved_demos_and_assets():
    from backend.projects.repository import DEMOS
    from backend.projects.visuals import load_demo_visuals

    visuals = load_demo_visuals()
    assert set(visuals) == APPROVED
    assert set(visuals) <= set(DEMOS)
    for demo_id, item in visuals.items():
        assert item.image_url == f"/circuit-schematics/{demo_id}.png"
        assert item.original_url.startswith("https://")
        assert item.source_repo.startswith("https://")
        assert item.license_evidence_url.startswith("https://")
        assert len(item.source_commit) == 40
        assert item.license.strip()
        assert item.attribution.strip()
        assert len(item.source_sha256) == 64
        asset = ROOT / "frontend/public" / item.image_url.removeprefix("/")
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == item.sha256
    assert visuals["franzininho_diy"].source_repo == "https://github.com/Franzininho/franzininho-diy-board"


@pytest.mark.parametrize("change", ["missing_demo", "unknown_demo", "wrong_path", "missing_asset", "hash_mismatch"])
def test_visual_catalog_rejects_broken_assets_and_demo_sets(tmp_path, monkeypatch, change):
    from backend.projects import visuals

    catalog = json.loads((ROOT / "data/circuits/visuals.json").read_text(encoding="utf-8"))
    public = tmp_path / "public"
    for demo_id, item in catalog.items():
        target = public / item["image_url"].lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"test asset")
        item["sha256"] = hashlib.sha256(b"test asset").hexdigest()
    if change == "missing_demo":
        del catalog[SAMPLE]
    elif change == "unknown_demo":
        catalog["unknown"] = dict(catalog[SAMPLE])
    elif change == "wrong_path":
        catalog[SAMPLE]["image_url"] = "/circuit-schematics/../private.png"
    elif change == "missing_asset":
        (public / f"circuit-schematics/{SAMPLE}.png").unlink()
    else:
        (public / f"circuit-schematics/{SAMPLE}.png").write_bytes(b"changed")
    catalog_path = tmp_path / "visuals.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setattr(visuals, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(visuals, "PUBLIC_ROOT", public)
    monkeypatch.setattr(visuals, "DIST_ROOT", tmp_path / "missing-dist", raising=False)
    visuals.load_demo_visuals.cache_clear()
    try:
        with pytest.raises(ValueError):
            visuals.load_demo_visuals()
    finally:
        visuals.load_demo_visuals.cache_clear()


@pytest.mark.parametrize("build_state", ["dist_only", "dist_preferred", "development", "missing", "corrupt"])
def test_visual_catalog_validates_served_runtime_assets(tmp_path, monkeypatch, build_state):
    from backend.projects import visuals

    public = tmp_path / "public"
    dist = tmp_path / "dist"
    for demo_id in APPROVED:
        relative = Path("circuit-schematics") / f"{demo_id}.png"
        source = ROOT / "frontend/public" / relative
        if build_state != "dist_only":
            target = public / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"stale source" if build_state == "dist_preferred" else source.read_bytes())
        if build_state != "development":
            target = dist / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if demo_id == SAMPLE and build_state == "missing":
                continue
            target.write_bytes(b"corrupt build" if build_state == "corrupt" else source.read_bytes())
    monkeypatch.setattr(visuals, "PUBLIC_ROOT", public)
    monkeypatch.setattr(visuals, "DIST_ROOT", dist, raising=False)
    visuals.load_demo_visuals.cache_clear()
    try:
        if build_state in {"missing", "corrupt"}:
            with pytest.raises(ValueError, match="회로도 자산"):
                visuals.load_demo_visuals()
        else:
            assert set(visuals.load_demo_visuals()) == APPROVED
    finally:
        visuals.load_demo_visuals.cache_clear()


@pytest.mark.parametrize("field,value", [
    ("original_url", "http://example.org/image.png"),
    ("source_repo", "javascript:alert(1)"),
    ("license_evidence_url", "file:///private/LICENSE"),
    ("source_commit", "A" * 40), ("sha256", "0" * 63), ("source_sha256", "A" * 64),
    ("license", " "), ("attribution", ""), ("local_path", "C:/private"),
])
def test_visual_record_rejects_invalid_or_private_metadata(field, value):
    from backend.projects.visuals import DemoVisualRecord

    record = json.loads((ROOT / "data/circuits/visuals.json").read_text(encoding="utf-8"))[SAMPLE]
    record[field] = value
    with pytest.raises(ValueError):
        DemoVisualRecord.model_validate(record)


def test_visual_record_requires_original_source_hash():
    from backend.projects.visuals import DemoVisualRecord

    record = json.loads((ROOT / "data/circuits/visuals.json").read_text(encoding="utf-8"))[SAMPLE]
    del record["source_sha256"]
    with pytest.raises(ValueError):
        DemoVisualRecord.model_validate(record)
