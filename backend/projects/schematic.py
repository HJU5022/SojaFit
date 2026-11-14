"""검증된 KiCad 원본 회로도를 PDF로 변환하는 격리 실행기."""
from __future__ import annotations

import os
import base64
import binascii
from typing import Any
import subprocess
from pathlib import Path

from backend.projects.schematic_source import ExternalSchematicInvalidSource, ExternalSchematicUpstreamError

COMMAND_TIMEOUT_SECONDS = 30
KICAD_CLI = os.getenv("KICAD_CLI", "kicad-cli")
RENDERER_MAX_SHEETS = 20
RENDERER_MAX_RESPONSE_BYTES = 20 * 1024 * 1024


class InvalidKicadProject(ValueError):
    """KiCad PDF 변환 결과가 유효하지 않다."""


class KicadServiceUnavailable(RuntimeError):
    """KiCad CLI를 실행할 수 없거나 제한 시간 안에 끝나지 않았다."""


def run_kicad_pdf(root: Path, output: Path) -> tuple[str, Path]:
    """검증한 root 회로도와 자식 시트를 한 PDF로 내보낸다."""
    pdf = output / "schematic.pdf"
    home = output / "home"
    home.mkdir()
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", os.defpath)}
    try:
        version = subprocess.run(
            [KICAD_CLI, "--version"], check=True, capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SECONDS, env=env,
        ).stdout.strip()
        command = [KICAD_CLI, "sch", "export", "pdf", "--output", str(pdf), str(root)]
        if os.name == "posix":
            command = ["prlimit", "--as=2147483648", "--fsize=20971520", "--", *command]
        subprocess.run(command, cwd=root.parent, check=True, env=env,
                       timeout=COMMAND_TIMEOUT_SECONDS, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        raise KicadServiceUnavailable("KiCad 변환 서비스를 사용할 수 없습니다.") from None
    except subprocess.CalledProcessError:
        raise InvalidKicadProject("KiCad PDF를 변환할 수 없습니다.") from None
    return version, pdf


def _source_payload(source: Any) -> dict[str, Any]:
    """렌더러로 보낼 수 있는 검증된 source의 제한된 직렬화."""
    fields = ("repository", "commit", "license", "attribution", "repository_url", "source_url",
              "source_file", "asset_kind", "asset_paths", "root_schematic", "expected_sheets")
    payload = {field: getattr(source, field, None) for field in fields}
    if not isinstance(payload["repository"], str) or not isinstance(payload["commit"], str):
        raise ValueError("invalid schematic source")
    if payload["asset_kind"] != "kicad" or not isinstance(payload["asset_paths"], tuple):
        raise ValueError("renderer accepts KiCad sources only")
    if len(payload["asset_paths"]) > RENDERER_MAX_SHEETS:
        raise ValueError("invalid schematic files")
    if any(not isinstance(path, str) for path in payload["asset_paths"]):
        raise ValueError("invalid schematic files")
    if not isinstance(payload["expected_sheets"], int) or not 1 <= payload["expected_sheets"] <= RENDERER_MAX_SHEETS:
        raise ValueError("invalid sheet count")
    payload["asset_paths"] = list(payload["asset_paths"])
    return payload


def _renderer_headers(url: str) -> dict[str, str]:
    """Cloud Run에서는 메타데이터 서버 ID token을 audience로 발급한다."""
    if os.getenv("K_SERVICE") and not url.startswith("https://"):
        raise KicadServiceUnavailable("KiCad 렌더러 주소는 HTTPS여야 합니다.")
    if os.getenv("K_SERVICE") and url.startswith("https://"):
        try:
            import httpx
            response = httpx.get(
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity",
                params={"audience": url.rstrip("/")},
                headers={"Metadata-Flavor": "Google"}, timeout=5, trust_env=False,
            )
            response.raise_for_status()
            token = response.text.strip()
            if not token:
                raise ValueError("empty identity token")
            return {"Authorization": f"Bearer {token}"}
        except Exception as exc:
            raise KicadServiceUnavailable("KiCad 렌더러 인증을 준비할 수 없습니다.") from exc
    return {}


def render_remote_kicad(source: Any, *, client: Any = None) -> tuple[bytes, ...]:
    """KiCad 원본만 별도 renderer에 보내고 PNG 시트를 검증해 돌려받는다."""
    import httpx
    url = os.getenv("KICAD_RENDERER_URL", "").rstrip("/")
    if not url or not url.startswith(("http://", "https://")):
        raise KicadServiceUnavailable("KiCad 렌더러가 설정되지 않았습니다.")
    body = {"source": _source_payload(source)}
    owned = client is None
    if owned:
        client = httpx.Client(timeout=90, follow_redirects=False, trust_env=False)
    try:
        response = client.post(url + "/render", json=body, headers=_renderer_headers(url))
        if response.status_code == 422:
            raise ExternalSchematicInvalidSource("KiCad 원본이 유효하지 않습니다.")
        if response.status_code != 200:
            raise KicadServiceUnavailable("KiCad 렌더러가 변환에 실패했습니다.")
        data = response.json()
        sheets = data.get("sheets") if isinstance(data, dict) else None
        if not isinstance(sheets, list) or not 1 <= len(sheets) <= RENDERER_MAX_SHEETS:
            raise KicadServiceUnavailable("KiCad 렌더러 응답이 올바르지 않습니다.")
        result = []
        total = 0
        for encoded in sheets:
            if not isinstance(encoded, str):
                raise KicadServiceUnavailable("KiCad 렌더러 응답이 올바르지 않습니다.")
            raw = base64.b64decode(encoded, validate=True)
            total += len(raw)
            if total > RENDERER_MAX_RESPONSE_BYTES:
                raise KicadServiceUnavailable("KiCad 렌더러 응답이 올바르지 않습니다.")
            try:
                from backend.projects.schematic_render import _valid_png
                _valid_png(raw)
            except Exception as exc:
                raise KicadServiceUnavailable("KiCad 렌더러 응답이 올바르지 않습니다.") from exc
            result.append(raw)
        expected = body["source"]["expected_sheets"]
        if len(result) != expected:
            raise KicadServiceUnavailable("KiCad 렌더러 시트 수가 다릅니다.")
        return tuple(result)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, binascii.Error) as exc:
        raise KicadServiceUnavailable("KiCad 렌더러에 연결할 수 없습니다.") from exc
    finally:
        if owned:
            client.close()


def _renderer_source(payload: Any):
    from backend.projects.schematic_source import VerifiedSchematicSource
    if not isinstance(payload, dict):
        raise ValueError("invalid source")
    required = ("repository", "commit", "license", "attribution", "repository_url", "source_url",
                "source_file", "asset_kind", "asset_paths", "root_schematic", "expected_sheets")
    if any(key not in payload for key in required):
        raise ValueError("invalid source")
    if payload["asset_kind"] != "kicad" or not isinstance(payload["asset_paths"], list):
        raise ValueError("renderer accepts KiCad sources only")
    if len(payload["asset_paths"]) > RENDERER_MAX_SHEETS:
        raise ValueError("invalid schematic files")
    if any(not isinstance(path, str) for path in payload["asset_paths"]):
        raise ValueError("invalid schematic files")
    if type(payload["expected_sheets"]) is not int or not 1 <= payload["expected_sheets"] <= RENDERER_MAX_SHEETS:
        raise ValueError("invalid sheet count")
    values = {key: payload[key] for key in required if key not in {"asset_paths", "expected_sheets"}}
    values["asset_paths"] = tuple(payload["asset_paths"])
    values["expected_sheets"] = payload["expected_sheets"]
    return VerifiedSchematicSource(**values)


try:
    from fastapi import FastAPI, HTTPException
    app = FastAPI()

    @app.get("/health")
    def renderer_health():
        return {"status": "ok", "kicad": True}

    @app.post("/render")
    def renderer_render(body: dict[str, Any]):
        try:
            source = _renderer_source(body.get("source"))
            from backend.projects.schematic_render import _valid_png, render_external_schematic
            sheets = render_external_schematic(source)
            sheets = tuple(_valid_png(sheet) for sheet in sheets)
            encoded = [base64.b64encode(sheet).decode("ascii") for sheet in sheets]
            if sum(len(sheet) for sheet in sheets) > RENDERER_MAX_RESPONSE_BYTES:
                raise ValueError("response too large")
            return {"sheets": encoded}
        except (ValueError, InvalidKicadProject, ExternalSchematicInvalidSource):
            raise HTTPException(status_code=422, detail="invalid KiCad source") from None
        except (KicadServiceUnavailable, ExternalSchematicUpstreamError, OSError):
            raise HTTPException(status_code=503, detail="KiCad renderer unavailable") from None
except ImportError:  # pragma: no cover - dependency is present in the service image
    app = None
