"""외부 원본 회로도 HTTP 경계: 인증·입력 검증·공개 오류만 처리한다.

검색 공급자 호출과 결과 정제는 backend/projects/external_circuit_search.py에 맡긴다.
검색 결과는 저장하지 않으며 성공과 오류 응답 모두 no-store로 전달한다.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from backend import auth
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


class ExternalSchematicResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str
    commit: str
    license: str
    attribution: str
    repository_url: str
    source_url: str
    source_file: str
    images: list[ExternalSchematicImage]


def _schematic_call(function, *args):
    try:
        return function(*args)
    except (ExternalSchematicNotFound, ExternalSchematicInvalidToken):
        raise ApiError(404, "검증된 완성 회로도를 찾지 못했습니다.", code="SCHEMATIC_NOT_FOUND") from None
    except ExternalSchematicRateLimited as error:
        raise HTTPException(503, "외부 회로도를 사용할 수 없습니다.",
                            headers={"Retry-After": str(error.retry_after)}) from None
    except (ExternalSchematicConfigurationError, ExternalCircuitSearchDisabled, ExternalCircuitSearchConfigurationError):
        raise HTTPException(503, "외부 회로도를 사용할 수 없습니다.") from None
    except (ExternalSchematicUpstreamError, ExternalCircuitSearchError):
        raise HTTPException(502, "지금은 외부 회로도를 불러올 수 없습니다.") from None


@router.get("/schematics", dependencies=[Depends(auth.current_user_id)], response_model=ExternalSchematicResponse)
def external_schematic_manifest(
    response: Response,
    q: Annotated[str, Query(min_length=2, max_length=200), BeforeValidator(str.strip)],
):
    response.headers["Cache-Control"] = "private, no-store"
    manifest = _schematic_call(find_external_schematic, q)
    return ExternalSchematicResponse(
        project=manifest.project, commit=manifest.commit, license=manifest.license,
        attribution=manifest.attribution, repository_url=manifest.repository_url,
        source_url=manifest.source_url, source_file=manifest.source_file,
        images=[ExternalSchematicImage(sheet=i, url=f"/api/external-circuits/schematics/{manifest.token}/{i}")
                for i in range(manifest.sheet_count)],
    )


@router.get(
    "/schematics/{signed_token}/{sheet_index}", dependencies=[Depends(auth.current_user_id)],
    response_class=Response,
    responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
)
def external_schematic_sheet(signed_token: str, sheet_index: int):
    if sheet_index < 0:
        raise ApiError(404, "검증된 완성 회로도를 찾지 못했습니다.", code="SCHEMATIC_NOT_FOUND")
    png = _schematic_call(load_external_schematic_sheet, signed_token, sheet_index)
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline",
    })
