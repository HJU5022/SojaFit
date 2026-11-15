"""외부 원본 회로도 HTTP 경계: 인증·입력 검증·공개 오류만 처리한다.

검색 공급자 호출과 결과 정제는 backend/projects/external_circuit_search.py에 맡긴다.
검색 결과는 저장하지 않으며 성공과 오류 응답 모두 no-store로 전달한다.
"""
import re
from uuid import UUID
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from backend import auth
from backend.projects.repository import ProjectRepository, ProjectNotFound
from backend.projects.netlist import circuit_fingerprint, InvalidNetlist
from backend.errors import ApiError
from backend.projects.external_schematic import find_external_schematic, load_external_schematic_sheet
from backend.projects.schematic_source import (
    ExternalSchematicConfigurationError, ExternalSchematicInvalidToken, ExternalSchematicNotFound,
    ExternalSchematicRateLimited, ExternalSchematicUpstreamError,
)
from backend.projects.external_circuit_search import (
    ExternalCircuitSearchConfigurationError,
    ExternalCircuitSearchDisabled,
    ExternalCircuitSearchError,
)

router = APIRouter(prefix="/api/external-circuits", tags=["external-circuits"])


class ExternalSchematicImage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sheet: int = Field(ge=0)
    url: str


class ExternalSchematicChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    source_url: str
    source_type: Literal["manufacturer_official", "public_web", "community"]
    revision: str | None


class ExternalSchematicResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str | None
    commit: str | None
    license: str
    attribution: str
    repository_url: str | None
    source_url: str
    source_file: str
    source_type: Literal["manufacturer_official", "community", "public_web"]
    evidence_grade: Literal[2, 3] | None
    manufacturer: str | None
    model: str | None
    revision: str | None
    source_sha256: str | None
    license_evidence_url: str | None
    images: list[ExternalSchematicImage]
    choices: list[ExternalSchematicChoice] = Field(default_factory=list)
    circuit_version: int | None = None

    @model_validator(mode="after")
    def validate_provenance(self):
        if self.evidence_grade == 2:
            if self.source_type != "manufacturer_official" or not isinstance(self.source_sha256, str):
                raise ValueError("2등급 공식 회로도는 제조사 출처와 원본 SHA-256이 필요합니다.")
            if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
                raise ValueError("2등급 원본 SHA-256 형식이 올바르지 않습니다.")
        elif self.evidence_grade == 3 and self.source_type != "community":
            raise ValueError("3등급 회로도는 커뮤니티 출처로만 표시할 수 있습니다.")
        elif self.evidence_grade is None and self.source_type != "public_web":
            raise ValueError("출처 미확인 회로도는 등급을 지정할 수 없습니다.")
        return self


def _schematic_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ExternalSchematicNotFound as error:
        messages = {
            "no_candidates": "조건에 맞는 원본 회로도 검색 결과가 없습니다. 검색어를 바꿔 보세요.",
            "validation_failed": "회로도 후보를 찾았지만 제품 식별 또는 원본 파일 검증을 통과하지 못했습니다. 제조사와 정확한 모델명을 확인해 주세요.",
            'circuit_mismatch': '업로드한 회로와 부품·핀 연결이 일치하는 회로도를 확인하지 못했습니다. 다른 회로도는 원본으로 연결하지 않습니다.',
        }
        raise ApiError(404, messages.get(error.reason, "검증된 완성 회로도를 찾지 못했습니다."),
                       code="SCHEMATIC_NOT_FOUND", headers={"X-Schematic-Failure": error.reason}) from None
    except ExternalSchematicInvalidToken:
        raise ApiError(404, "검증된 완성 회로도를 찾지 못했습니다.", code="SCHEMATIC_NOT_FOUND") from None
    except ExternalSchematicRateLimited as error:
        raise HTTPException(503, "외부 회로도를 사용할 수 없습니다.",
                            headers={"Retry-After": str(error.retry_after)}) from None
    except (ExternalSchematicConfigurationError, ExternalCircuitSearchDisabled, ExternalCircuitSearchConfigurationError):
        raise HTTPException(503, "외부 회로도를 사용할 수 없습니다.") from None
    except (ExternalSchematicUpstreamError, ExternalCircuitSearchError):
        raise HTTPException(502, "지금은 외부 회로도를 불러올 수 없습니다.") from None


def _project_circuit(user_id, project_id, circuit_version, thread_id, reference_only=False):
    if project_id is None:
        if not reference_only or circuit_version is not None or thread_id is not None:
            raise HTTPException(422, '프로젝트와 회로 버전을 함께 지정해 주세요.')
        return None
    if reference_only:
        raise HTTPException(422, '참고 자료 검색과 프로젝트 원본 조회를 함께 지정할 수 없습니다.')
    if circuit_version is None:
        raise HTTPException(422, '회로 버전이 필요합니다.')
    try:
        project = ProjectRepository().get_owned(user_id, project_id, thread_id)
    except ProjectNotFound:
        raise HTTPException(404, '프로젝트 회로를 찾을 수 없습니다.') from None
    if project.circuit_version != circuit_version:
        raise HTTPException(409, '회로 버전이 변경됐습니다. 회로도 창을 다시 열어 주세요.')
    try:
        circuit_fingerprint(project.connections)
    except InvalidNetlist:
        raise ApiError(404, '대조할 회로 연결 정보가 없습니다.', code='SCHEMATIC_NOT_FOUND') from None
    return project


@router.get("/schematics", response_model=ExternalSchematicResponse)
def external_schematic_manifest(
    response: Response,
    q: Annotated[str, Query(min_length=2, max_length=200), BeforeValidator(str.strip)],
    user_id: Annotated[int, Depends(auth.current_user_id)],
    source_url: Annotated[str | None, Query(max_length=2048)] = None,
    project_id: Annotated[int | None, Query(ge=1)] = None,
    circuit_version: Annotated[int | None, Query(ge=1)] = None,
    thread_id: UUID | None = None,
    reference_only: bool = False,
    component_type: Literal['diode'] | None = None,
):
    response.headers["Cache-Control"] = "private, no-store"
    project = _project_circuit(user_id, project_id, circuit_version, thread_id, reference_only)
    if component_type is not None and (project is not None or len(q) > 194):
        raise HTTPException(422, '다이오드 검색은 194자 이하 참고 자료 조회로만 사용할 수 있습니다.')
    manifest = (_schematic_call(find_external_schematic, q, source_url, connections=project.connections) if project else
                _schematic_call(find_external_schematic, q, source_url, component_type) if component_type else
                _schematic_call(find_external_schematic, q, source_url) if source_url is not None
                else _schematic_call(find_external_schematic, q))
    scope = f'?project_id={project_id}&circuit_version={circuit_version}' if project else '?reference_only=true'
    if project and thread_id:
        scope += f'&thread_id={thread_id}'
    return ExternalSchematicResponse(
        project=manifest.project, commit=manifest.commit, license=manifest.license,
        attribution=manifest.attribution, repository_url=manifest.repository_url,
        source_url=manifest.source_url, source_file=manifest.source_file,
        source_type=manifest.source_type, evidence_grade=manifest.evidence_grade,
        manufacturer=manifest.manufacturer, model=manifest.model, revision=manifest.revision,
        source_sha256=manifest.source_sha256, license_evidence_url=manifest.license_evidence_url,
        images=[ExternalSchematicImage(sheet=i, url=f"/api/external-circuits/schematics/{manifest.token}/{i}{scope}")
                for i in range(manifest.sheet_count)],
        choices=[ExternalSchematicChoice.model_validate(choice.__dict__)
                 for choice in manifest.choices],
        circuit_version=circuit_version if project else None,
    )


@router.get(
    "/schematics/{signed_token}/{sheet_index}",
    response_class=Response,
    responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
)
def external_schematic_sheet(signed_token: str, sheet_index: int,
    user_id: Annotated[int, Depends(auth.current_user_id)],
    project_id: Annotated[int | None, Query(ge=1)] = None,
    circuit_version: Annotated[int | None, Query(ge=1)] = None,
    thread_id: UUID | None = None, reference_only: bool = False):
    if sheet_index < 0:
        raise ApiError(404, "검증된 완성 회로도를 찾지 못했습니다.", code="SCHEMATIC_NOT_FOUND")
    project = _project_circuit(user_id, project_id, circuit_version, thread_id, reference_only)
    png = (_schematic_call(load_external_schematic_sheet, signed_token, sheet_index, connections=project.connections)
           if project else _schematic_call(load_external_schematic_sheet, signed_token, sheet_index))
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline",
    })
