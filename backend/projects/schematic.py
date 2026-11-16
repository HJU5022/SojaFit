"""검증된 KiCad 원본 회로도를 PDF로 변환하는 격리 실행기."""
from __future__ import annotations

import os
import base64
import binascii
import json
from typing import Any
import subprocess
from pathlib import Path

from backend.projects.schematic_source import (
    ExternalSchematicInvalidSource, ExternalSchematicRateLimited, ExternalSchematicUpstreamError,
)

COMMAND_TIMEOUT_SECONDS = 30
KICAD_CLI = os.getenv("KICAD_CLI", "kicad-cli")
RENDERER_MAX_SHEETS = 20
RENDERER_MAX_RESPONSE_BYTES = 20 * 1024 * 1024
UPLOAD_RENDER_SECONDS = 150


class InvalidKicadProject(ValueError):
    """KiCad PDF 변환 결과가 유효하지 않다."""


class KicadServiceUnavailable(RuntimeError):
    """KiCad CLI를 실행할 수 없거나 제한 시간 안에 끝나지 않았다."""


def run_kicad_pdf(root: Path, output: Path) -> tuple[str, Path]:
    return _run_export(root, output, 'pdf')


def run_kicad_netlist(root: Path, output: Path) -> Path:
    return _run_export(root, output, 'netlist')[1]


def _run_export(root: Path, output: Path, kind: str) -> tuple[str, Path]:
    """검증한 root 회로도와 자식 시트를 한 PDF로 내보낸다."""
    pdf = output / ('schematic.net' if kind == 'netlist' else 'schematic.pdf')
    home = output / "home"
    home.mkdir()
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", os.defpath)}
    try:
        version = subprocess.run(
            [KICAD_CLI, "--version"], check=True, capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SECONDS, env=env,
        ).stdout.strip()
        command = [KICAD_CLI, "sch", "export", kind, "--output", str(pdf)]
        if kind == 'netlist':
            command += ['--format', 'kicadsexpr']
        command.append(str(root))
        if os.name == "posix":
            command = ["prlimit", "--as=2147483648", '--fsize='+str(5*1024**2 if kind == 'netlist' else 20*1024**2), "--", *command]
        subprocess.run(command, cwd=root.parent, check=True, env=env,
                       timeout=COMMAND_TIMEOUT_SECONDS, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        raise KicadServiceUnavailable("KiCad 변환 서비스를 사용할 수 없습니다.") from None
    except subprocess.CalledProcessError:
        raise InvalidKicadProject("KiCad PDF를 변환할 수 없습니다.") from None
    return version, pdf


# 렌더러로 보내고 렌더러가 받는 source 칸. 보내는 쪽(_source_payload)과 받는 쪽(_renderer_source)이 같은 목록을 쓴다
SOURCE_FIELDS = ("repository", "commit", "license", "attribution", "repository_url", "source_url",
                 "source_file", "asset_kind", "asset_paths", "root_schematic", "expected_sheets")


def _source_payload(source: Any) -> dict[str, Any]:
    """렌더러로 보낼 수 있는 검증된 source의 제한된 직렬화."""
    payload = {field: getattr(source, field, None) for field in SOURCE_FIELDS}
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


def render_remote_kicad(source: Any, *, connections=None, client: Any = None) -> tuple[bytes, ...]:
    """KiCad 원본만 별도 renderer에 보내고 PNG 시트를 검증해 돌려받는다."""
    import httpx
    url = os.getenv("KICAD_RENDERER_URL", "").rstrip("/")
    if not url or not url.startswith(("http://", "https://")):
        raise KicadServiceUnavailable("KiCad 렌더러가 설정되지 않았습니다.")
    body = {"source": _source_payload(source)}
    if connections is not None:
        body['include_netlist'] = True
    owned = client is None
    if owned:
        client = httpx.Client(timeout=90, follow_redirects=False, trust_env=False)
    try:
        from backend.projects.external_circuit_search import read_bounded_body
        from backend.projects.netlist import MAX_BYTES
        with client.stream('POST', url + '/render', json=body,
                           headers={**_renderer_headers(url), 'Accept-Encoding': 'identity'}) as response:
            raw_response = read_bounded_body(response, RENDERER_MAX_RESPONSE_BYTES * 4 // 3 + MAX_BYTES + 65536)
        if response.status_code == 422:
            raise ExternalSchematicInvalidSource("KiCad 원본이 유효하지 않습니다.")
        if response.status_code == 429 or (
                response.status_code == 503 and "retry-after" in response.headers) or (
                response.status_code == 403 and (
                    response.headers.get("x-ratelimit-remaining") == "0"
                    or "retry-after" in response.headers)):
            try:
                retry_after = min(3600, max(1, int(response.headers.get("retry-after", "60"))))
            except ValueError:
                retry_after = 60
            raise ExternalSchematicRateLimited(
                retry_after, host=url.split("/", 3)[2], phase="renderer",
                status_code=response.status_code,
            )
        if response.status_code != 200:
            raise KicadServiceUnavailable("KiCad 렌더러가 변환에 실패했습니다.")
        data = json.loads(raw_response)
        if connections is not None:
            from backend.projects.netlist import MAX_BYTES, InvalidNetlist, same_circuit
            candidate = data.get('connections') if isinstance(data,dict) else None
            try:
                if len(json.dumps(candidate).encode()) > MAX_BYTES or not same_circuit(candidate, connections):
                    raise ExternalSchematicInvalidSource('원격 원본과 업로드 회로가 일치하지 않습니다.')
            except (InvalidNetlist, TypeError, ValueError):
                raise ExternalSchematicInvalidSource('원격 원본 연결을 확인할 수 없습니다.') from None
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


def export_uploaded_kicad(text: str, *, client: Any = None) -> tuple[bytes, tuple[bytes, ...]]:
    """업로드한 .kicad_sch 원문을 렌더러에 보내 (KiCad 넷리스트 원문, PNG 시트)를 받는다.

    렌더러 422는 InvalidKicadProject, 설정 없음 · 연결 실패 · 시간 초과 · 그 밖의 응답은 KicadServiceUnavailable.
    """
    import time
    import httpx
    from backend.projects.external_circuit_search import read_bounded_body
    from backend.projects.netlist import MAX_BYTES
    url = os.getenv("KICAD_RENDERER_URL", "").rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise KicadServiceUnavailable("KiCad 렌더러가 설정되지 않았습니다.")
    owned = client is None
    if owned:
        client = httpx.Client(timeout=90, follow_redirects=False, trust_env=False)
    try:
        with client.stream('POST', url + '/render', json={'schematic': text},
                           headers={**_renderer_headers(url), 'Accept-Encoding': 'identity'}) as response:
            # [왜] 읽기 timeout은 조각마다라 전체 시간도 막는다(KiCad 변환 4번 · 그림 1번이 각 30초 상한)
            raw_response = read_bounded_body(response, RENDERER_MAX_RESPONSE_BYTES * 4 // 3 + MAX_BYTES * 2 + 65536,
                                             deadline=time.monotonic() + UPLOAD_RENDER_SECONDS)
        if response.status_code == 422:
            raise InvalidKicadProject("KiCad 회로도를 읽을 수 없습니다.")
        if response.status_code != 200:
            raise KicadServiceUnavailable("KiCad 렌더러가 변환에 실패했습니다.")
        data = json.loads(raw_response)
        netlist, sheets = data['netlist'].encode('utf-8'), data['sheets']
        if len(netlist) > MAX_BYTES or not isinstance(sheets, list) or len(sheets) != 1:
            raise ValueError('invalid renderer response')
        from backend.projects.schematic_render import _valid_png
        return netlist, tuple(_valid_png(base64.b64decode(sheet, validate=True)) for sheet in sheets)
    except InvalidKicadProject:
        raise
    except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError, AttributeError, binascii.Error,
            ExternalSchematicInvalidSource) as exc:
        raise KicadServiceUnavailable("KiCad 렌더러에 연결할 수 없습니다.") from exc
    finally:
        if owned:
            client.close()


def _renderer_source(payload: Any):
    from backend.projects.schematic_source import VerifiedSchematicSource
    if not isinstance(payload, dict):
        raise ValueError("invalid source")
    if any(key not in payload for key in SOURCE_FIELDS):
        raise ValueError("invalid source")
    if payload["asset_kind"] != "kicad" or not isinstance(payload["asset_paths"], list):
        raise ValueError("renderer accepts KiCad sources only")
    if len(payload["asset_paths"]) > RENDERER_MAX_SHEETS:
        raise ValueError("invalid schematic files")
    if any(not isinstance(path, str) for path in payload["asset_paths"]):
        raise ValueError("invalid schematic files")
    if type(payload["expected_sheets"]) is not int or not 1 <= payload["expected_sheets"] <= RENDERER_MAX_SHEETS:
        raise ValueError("invalid sheet count")
    values = {key: payload[key] for key in SOURCE_FIELDS if key not in {"asset_paths", "expected_sheets"}}
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
            if set(body) == {'schematic'}:
                # 업로드한 회로도 한 장(#52): 넷리스트 원문과 PNG를 함께 돌려준다. GitHub 원본(source)과 섞지 않는다
                if not isinstance(body['schematic'], str):
                    raise ValueError('invalid renderer request')
                from backend.projects.schematic_render import render_uploaded_schematic
                netlist, sheets = render_uploaded_schematic(body['schematic'])
                return {'sheets': [base64.b64encode(sheet).decode('ascii') for sheet in sheets],
                        'netlist': netlist.decode('utf-8')}
            if set(body)-{'source','include_netlist'} or type(body.get('include_netlist',False)) is not bool:
                raise ValueError('invalid renderer request')
            source = _renderer_source(body.get("source"))
            from backend.projects.schematic_render import _valid_png, render_external_schematic
            captured = []
            sheets = (render_external_schematic(source,connection_consumer=captured.append)
                      if body.get('include_netlist') else render_external_schematic(source))
            sheets = tuple(_valid_png(sheet) for sheet in sheets)
            encoded = [base64.b64encode(sheet).decode("ascii") for sheet in sheets]
            if sum(len(sheet) for sheet in sheets) > RENDERER_MAX_RESPONSE_BYTES:
                raise ValueError("response too large")
            result = {"sheets": encoded}
            if body.get('include_netlist'):
                if len(captured)!=1:raise ValueError('candidate netlist missing')
                result['connections'] = json.loads(json.dumps(captured[0],default=dict))
            return result
        except (ValueError, InvalidKicadProject, ExternalSchematicInvalidSource):
            raise HTTPException(status_code=422, detail="invalid KiCad source") from None
        except ExternalSchematicRateLimited as error:
            raise HTTPException(
                status_code=503, detail="KiCad renderer unavailable",
                headers={"Retry-After": str(error.retry_after)},
            ) from None
        except (KicadServiceUnavailable, ExternalSchematicUpstreamError, OSError):
            raise HTTPException(status_code=503, detail="KiCad renderer unavailable") from None
except ImportError:  # pragma: no cover - dependency is present in the service image
    app = None
