import json

import pytest


def test_catalog_contains_all_collected_circuits_and_resolves_connections():
    from backend.projects.catalog import load_catalog

    catalog = load_catalog()

    assert len(catalog) == 15
    assert len({item.id for item in catalog}) == len(catalog)
    assert {item.id for item in catalog} >= {
        "breadboard_supply", "mosfet_driver", "attiny85_dev", "pro_micro",
        "franzininho_diy", "attiny85_time_switch",
    }
    assert all(item.connections_path.is_file() for item in catalog)


def test_catalog_rejects_duplicate_ids(tmp_path, monkeypatch):
    from backend.projects import catalog

    bad = tmp_path / "catalog.json"
    bad.write_text('{"a":{"name":"A","connections_path":"data/circuits/ok.json"},"a":{"name":"B","connections_path":"../secret.json"}}', encoding="utf-8")
    monkeypatch.setattr(catalog, "CATALOG_PATH", bad)
    catalog.load_catalog.cache_clear()

    with pytest.raises(ValueError, match="중복"):
        catalog.load_catalog()
    catalog.load_catalog.cache_clear()


@pytest.mark.parametrize("circuit_id", ["../escape", "Uppercase", "space id"])
def test_catalog_rejects_ids_that_are_not_safe_asset_slugs(tmp_path, monkeypatch, circuit_id):
    from backend.projects import catalog

    connections = catalog.load_catalog()[0].connections_path
    manifest = tmp_path / "catalog.json"
    manifest.write_text(json.dumps({circuit_id: {"name": "unsafe", "connections_path": str(connections)}}), encoding="utf-8")
    monkeypatch.setattr(catalog, "CATALOG_PATH", manifest)
    catalog.load_catalog.cache_clear()

    with pytest.raises(ValueError, match="id"):
        catalog.load_catalog()
    catalog.load_catalog.cache_clear()
