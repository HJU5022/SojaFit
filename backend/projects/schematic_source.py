"""공개 회로 원본의 불변 식별자와 서비스 오류."""
from dataclasses import dataclass
from hashlib import sha256
from math import ceil
import os
from threading import Lock
import time
from typing import Literal


ALLOWED_LICENSES = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-3.0", "CC-BY-SA-4.0",
    "CERN-OHL-P-2.0", "CERN-OHL-W-2.0", "CERN-OHL-S-2.0",
    "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
})

# SPDX deprecated identifiers with an unambiguous current replacement.
_DEPRECATED_LICENSE_ALIASES = {
    "GPL-2.0": "GPL-2.0-only",
    "GPL-3.0": "GPL-3.0-only",
}


def normalize_license_id(value: str | None) -> str | None:
    """Return the canonical SPDX identifier for an unambiguous alias."""
    return _DEPRECATED_LICENSE_ALIASES.get(value, value) if isinstance(value, str) else None


@dataclass(frozen=True)
class VerifiedSchematicSource:
    repository: str
    commit: str
    license: str
    attribution: str
    repository_url: str
    source_url: str
    source_file: str
    asset_kind: Literal["png", "svg", "pdf", "kicad"]
    asset_paths: tuple[str, ...]
    root_schematic: str
    expected_sheets: int = 1
    source_type: Literal["manufacturer_official", "community", "public_web"] = "community"
    evidence_grade: Literal[2, 3] | None = 3
    manufacturer: str | None = None
    model: str | None = None
    revision: str | None = None
    source_sha256: str | None = None
    license_evidence_url: str | None = None
    circuit_sha256: str | None = None


class ExternalSchematicError(RuntimeError):
    """호출자에게 외부 응답 본문을 노출하지 않는 오류."""


class ExternalSchematicConfigurationError(ExternalSchematicError):
    pass


class ExternalSchematicUpstreamError(ExternalSchematicError):
    pass


class ExternalSchematicInvalidSource(ExternalSchematicError):
    pass


class ExternalSchematicRateLimited(ExternalSchematicError):
    def __init__(self, retry_after: int, *, host: str | None = None,
                 phase: str = "download", status_code: int | None = None):
        super().__init__("공급자 호출 한도에 도달했습니다.")
        self.retry_after = min(max(1, retry_after), 3600)
        # 서버 내부 진단용 메타데이터이며 공개 API 응답에는 포함하지 않는다.
        self.host = host if isinstance(host, str) and host else None
        self.phase = phase if isinstance(phase, str) and phase else "download"
        self.status_code = status_code if type(status_code) is int else None


# shortcut: 프로세스별 제한 상태다. 여러 API worker의 전역 차단이 필요하면 공유 저장소로 옮긴다.
_RATE_LIMITS = {}
_RATE_LOCK = Lock()
_rate_clock = time.monotonic


def provider_rate_key(host):
    credential = sha256(os.getenv('GITHUB_TOKEN', '').strip().encode()).digest() if host == 'api.github.com' else b''
    return host, credential


def provider_rate_limit(host):
    """남은 대기 시간을 새 오류로 반환해 예외 traceback을 보관하지 않는다."""
    key = provider_rate_key(host)
    with _RATE_LOCK:
        entry = _RATE_LIMITS.get(key)
        if entry is None:
            return None
        deadline, phase, status = entry
        remaining = deadline - _rate_clock()
        if remaining <= 0:
            _RATE_LIMITS.pop(key, None)
            return None
    return ExternalSchematicRateLimited(ceil(remaining), host=host, phase=phase, status_code=status)


def remember_provider_limit(error):
    if not error.host:
        return
    key, now = provider_rate_key(error.host), _rate_clock()
    with _RATE_LOCK:
        for expired in [key for key, entry in _RATE_LIMITS.items() if entry[0] <= now]:
            _RATE_LIMITS.pop(expired)
        if key not in _RATE_LIMITS:
            _RATE_LIMITS[key] = (now + error.retry_after, error.phase, error.status_code)
        while len(_RATE_LIMITS) > 128:
            _RATE_LIMITS.pop(next(iter(_RATE_LIMITS)))


class ExternalSchematicNotFound(ExternalSchematicError):
    def __init__(self, *args, reason: str = "not_found"):
        super().__init__(*args)
        if reason not in {"not_found", "no_candidates", "validation_failed", 'circuit_mismatch', 'ambiguous_manufacturer'}:
            raise ValueError("유효하지 않은 회로도 실패 원인입니다.")
        self.reason = reason


class ExternalSchematicInvalidToken(ExternalSchematicError):
    pass
