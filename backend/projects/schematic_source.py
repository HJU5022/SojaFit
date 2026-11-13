"""공개 회로 원본의 불변 식별자와 서비스 오류."""
from dataclasses import dataclass
from typing import Literal


ALLOWED_LICENSES = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-3.0", "CC-BY-SA-4.0",
    "CERN-OHL-P-2.0", "CERN-OHL-W-2.0", "CERN-OHL-S-2.0",
    "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
})


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


class ExternalSchematicNotFound(ExternalSchematicError):
    pass


class ExternalSchematicInvalidToken(ExternalSchematicError):
    pass
