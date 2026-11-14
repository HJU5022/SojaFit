"""인증된 완성 회로도 HTTP 경계와 모든 PNG 시트의 실제 외부 점검.

이미지는 메모리에서만 검사하고 key, signed token, 외부 응답 본문은 출력하지 않는다.
--force-kicad-fallback은 API 경계를 거치지 않고 로컬 KiCad CLI를 직접 렌더링한다.
배포된 원격 KiCad 렌더러 경로는 일반 API 쿼리 결과에서 source_type으로 구별한다.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import io
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image

from backend.projects.schematic_source import ALLOWED_LICENSES, VerifiedSchematicSource


FALLBACK_SOURCE = VerifiedSchematicSource(
    repository="tomasr8/attiny85-dev-board",
    commit="488b99063b6bdbafa0f367ecc25901b55c4c7144",
    license="MIT",
    attribution="tomasr8/attiny85-dev-board contributors",
    repository_url="https://github.com/tomasr8/attiny85-dev-board",
    source_url="https://github.com/tomasr8/attiny85-dev-board/tree/488b99063b6bdbafa0f367ecc25901b55c4c7144",
    source_file="attiny85.kicad_sch",
    asset_kind="kicad",
    asset_paths=(),
    root_schematic="attiny85.kicad_sch",
)


def _dimension(png):
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("sheet is not PNG")
    with Image.open(io.BytesIO(png)) as image:
        if image.format != "PNG":
            raise RuntimeError("sheet is not PNG")
        image.verify()
    with Image.open(io.BytesIO(png)) as image:
        if min(image.size) <= 0:
            raise RuntimeError("sheet dimensions are invalid")
        return list(image.size)


@contextmanager
def _http_boundary():
    from fastapi.testclient import TestClient
    from backend import auth
    from backend.main import app

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    try:
        # lifespan을 실행하지 않아 DB·대화 서비스 없이 실제 API와 실제 검색/렌더 서비스를 검사한다.
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def verify_query(query, client):
    response = client.get("/api/external-circuits/schematics", params={"q": query})
    if response.status_code != 200:
        raise RuntimeError(f"manifest HTTP {response.status_code}")
    if response.headers.get("cache-control") != "private, no-store":
        raise RuntimeError("manifest cache policy is invalid")
    manifest = response.json()
    official = manifest.get("source_type") == "manufacturer_official"
    if official:
        from backend.projects.visuals import load_demo_visuals
        allowed_licenses = {visual.license for visual in load_demo_visuals().values()}
    else:
        allowed_licenses = ALLOWED_LICENSES
    valid_source = (
        manifest["license"] in allowed_licenses
        and (official or bool(re.fullmatch(r"[0-9a-f]{40}", manifest.get("commit") or "")))
        and manifest["source_file"].lower().endswith(
            (".pdf", ".png", ".svg") if official else (".kicad_sch", ".sch")
        )
        and (manifest.get("evidence_grade") == 2 if official else manifest.get("evidence_grade") == 3)
        and (not official or bool(re.fullmatch(r"[0-9a-f]{64}", manifest.get("source_sha256") or "")))
    )
    if not valid_source or not manifest["images"]:
        raise RuntimeError("manifest source provenance is invalid")
    dimensions = []
    for index, sheet in enumerate(manifest["images"]):
        if sheet["sheet"] != index or not sheet["url"].startswith("/api/external-circuits/schematics/"):
            raise RuntimeError("manifest sheet order is invalid")
        response = client.get(sheet["url"])
        if response.status_code != 200:
            raise RuntimeError(f"sheet HTTP {response.status_code}")
        for name, expected in {
            "content-type": "image/png", "cache-control": "private, no-store",
            "x-content-type-options": "nosniff", "content-disposition": "inline",
        }.items():
            if response.headers.get(name) != expected:
                raise RuntimeError("sheet response headers are invalid")
        dimensions.append(_dimension(response.content))
    return {
        "query": query, "project": manifest["project"], "commit": manifest["commit"],
        "license": manifest["license"], "source_file": manifest["source_file"],
        "sheet_count": len(dimensions), "dimensions": dimensions,
    }


@contextmanager
def _provider_counts():
    from backend.projects import external_schematic

    service = external_schematic._SERVICE
    originals = {name: getattr(service, name) for name in ("search", "inspect", "render")}
    counts = Counter({name: 0 for name in originals})
    def counted(name, function):
        def call(*args, **kwargs):
            counts[name] += 1
            return function(*args, **kwargs)
        return call
    try:
        for name, function in originals.items():
            setattr(service, name, counted(name, function))
        yield counts
    finally:
        for name, function in originals.items():
            setattr(service, name, function)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append")
    parser.add_argument("--check-cache", action="store_true")
    parser.add_argument("--force-kicad-fallback", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.force_kicad_fallback:
            from backend.projects.schematic_render import render_external_schematic
            dimensions = [_dimension(png) for png in render_external_schematic(FALLBACK_SOURCE)]
            if not dimensions:
                raise RuntimeError("fallback returned no sheets")
            print(json.dumps({"mode": "kicad-local-direct", "renderer": "local-kicad-cli",
                "project": FALLBACK_SOURCE.repository,
                "commit": FALLBACK_SOURCE.commit, "license": FALLBACK_SOURCE.license,
                "source_file": FALLBACK_SOURCE.source_file, "sheet_count": len(dimensions),
                "dimensions": dimensions}, ensure_ascii=False))
            return 0
        with _http_boundary() as client, _provider_counts() as counts:
            for query in args.query or ["ATtiny85", "LM7805 power supply"]:
                before = counts.copy()
                result = verify_query(query, client)
                result["cold_calls"] = {name: counts[name] - before[name] for name in counts}
                if args.check_cache:
                    before = counts.copy()
                    warm = verify_query(query, client)
                    if warm != {key: value for key, value in result.items() if key != "cold_calls"}:
                        raise RuntimeError("cache result differs")
                    result["warm_calls"] = {name: counts[name] - before[name] for name in counts}
                    if any(result["warm_calls"].values()):
                        raise RuntimeError("cache hit invoked a provider")
                print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        # exception 메시지·traceback에는 URL/token/외부 본문이 섞일 수 있다.
        print(json.dumps({"ok": False, "error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
