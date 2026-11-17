"""외부 원본 회로도 HTTP 경계: 인증·입력 검증·공개 오류만 처리한다.

검색 · 검증 · 변환은 backend/projects/external_schematic.py(find_external_schematic)에 맡기고, 후보 정제는 그 아래 external_circuit_search.py가 한다.
검색 결과는 저장하지 않으며 성공과 오류 응답 모두 no-store로 전달한다.
"""
import re
from uuid import UUID
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, model_validator

from backend import auth
from backend.projects.repository import ProjectRepository, ProjectNotFound
from backend.projects.netlist import circuit_fingerprint, InvalidNetlist
from backend.errors import ApiError, code_for
from backend.api.conversations import analysis_service
from backend.projects.external_schematic import find_external_schematic, load_external_schematic_sheet
from backend.projects.schematic_source import (
    ExternalSchematicConfigurationError, ExternalSchematicInvalidToken, ExternalSchematicNotFound,
    ExternalSchematicRateLimited, ExternalSchematicUpstreamError,
)
from backend.projects.external_circuit_search import (
    ExternalCircuitSearchConfigurationError,
    ExternalCircuitSearchDisabled,
    ExternalCircuitSearchError,
    automatic_schematic_context,
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
        # [왜] 등급과 출처 종류가 어긋나면 화면에 잘못된 신뢰 표시가 나간다. 2등급=제조사 공식+원본 SHA-256, 3등급=커뮤니티, 등급 없음=공개 웹만 응답으로 내보낸다
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


SearchTerm = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]


class SchematicDialogueRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [
        {'question': 'RP2040 회로도들을 모두 소개해 주세요.', 'queries': ['RP2040'], 'reference_only': True}]})
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    queries: list[SearchTerm] = Field(min_length=1, max_length=3)
    project_id: int | None = Field(default=None, ge=1)
    circuit_version: int | None = Field(default=None, ge=1)
    thread_id: UUID | None = None
    reference_only: bool = True
    component_type: Literal['diode'] | None = None


class SchematicDialogueCandidate(ExternalSchematicChoice):
    candidate_id: str
    number: int
    queries: list[str]
    manufacturer: str | None = None
    model: str | None = None
    source_file: str | None = None
    evidence_grade: Literal[2, 3] | None = None
    source_sha256: str | None = None
    commit: str | None = None
    license: str | None = None
    attribution: str | None = None
    repository_url: str | None = None
    license_evidence_url: str | None = None
    selection_url: str


class SchematicDescription(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate_id: str
    text: str


class SchematicDialogue(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['generated', 'unavailable']
    mode: Literal['select', 'all', 'single']
    selection_required: bool
    message: str | None
    question: str | None
    descriptions: list[SchematicDescription]
    reason: str | None
    clarification_fields: list[str]


class SchematicSearchFailure(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str
    status_code: int
    code: str
    message: str
    retry_after: str | None = None


class SchematicDialogueResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    queries: list[str]
    count: int
    candidates: list[SchematicDialogueCandidate]
    dialogue: SchematicDialogue
    failures: list[SchematicSearchFailure]


def _schematic_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ExternalSchematicNotFound as error:
        messages = {
            "no_candidates": "조건에 맞는 원본 회로도 검색 결과가 없습니다. 검색어를 바꿔 보세요.",
            "validation_failed": "회로도 후보를 찾았지만 제품 식별 또는 원본 파일 검증을 통과하지 못했습니다. 제조사와 정확한 모델명을 확인해 주세요.",
            'circuit_mismatch': '업로드한 회로와 부품·핀 연결이 일치하는 회로도를 확인하지 못했습니다. 다른 회로도는 원본으로 연결하지 않습니다.',
            'ambiguous_manufacturer': '여러 제조사의 정상 공식 자료가 확인됐습니다. 검색어에 제조사 이름을 함께 입력해 주세요.',
        }
        raise ApiError(404, messages.get(error.reason, "검증된 완성 회로도를 찾지 못했습니다."),
                       code="SCHEMATIC_NOT_FOUND", headers={"X-Schematic-Failure": error.reason}) from None
    # [주의] 위조 · 만료 토큰을 따로 알리지 않고 없는 회로도와 같은 404로 답한다
    except ExternalSchematicInvalidToken:
        raise ApiError(404, "검증된 완성 회로도를 찾지 못했습니다.", code="SCHEMATIC_NOT_FOUND") from None
    # [주의] 외부 제공자의 한도 초과는 429가 아니라 503으로 보내고, 제공자가 준 대기 시간을 Retry-After에 싣는다
    except ExternalSchematicRateLimited as error:
        raise HTTPException(503, "외부 회로도를 사용할 수 없습니다.",
                            headers={"Retry-After": str(error.retry_after)}) from None
    except (ExternalSchematicConfigurationError, ExternalCircuitSearchDisabled, ExternalCircuitSearchConfigurationError):
        raise HTTPException(503, "외부 회로도를 사용할 수 없습니다.") from None
    except (ExternalSchematicUpstreamError, ExternalCircuitSearchError):
        raise HTTPException(502, "지금은 외부 회로도를 불러올 수 없습니다.") from None


def _project_circuit(user_id, project_id, circuit_version, thread_id, reference_only=False, *, require_connections=True):
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
    # [왜] 창을 연 뒤 회로가 새 버전으로 바뀌었으면 옛 버전 기준으로 대조한 회로도를 보이지 않고 다시 열게 한다
    if project.circuit_version != circuit_version:
        raise HTTPException(409, '회로 버전이 변경됐습니다. 회로도 창을 다시 열어 주세요.')
    # [왜] 원본 찾기는 회로 연결 지문으로 후보를 대조하므로 연결 정보가 없는 회로는 검색 전에 404로 끝낸다
    if require_connections:
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
    auto_search: bool = False,
):
    response.headers["Cache-Control"] = "private, no-store"
    context = automatic_schematic_context(q) if auto_search else 'original'
    project = _project_circuit(user_id, project_id, circuit_version, thread_id, reference_only,
                               require_connections=context == 'original')
    if auto_search:
        if project is None or component_type is not None:
            raise HTTPException(422, '자동 검색에는 프로젝트와 회로 버전만 지정해 주세요.')
        # [왜] 자동 찾기의 검색어가 제조사 · 부품 · 보드 이름처럼 참고 자료로 보이면 업로드 회로와 대조하지 않고 참고 자료 검색으로 바꾼다
        if context != 'original':
            project = None
            component_type = 'diode' if context == 'diode' else None
    # [왜] 194 = 200 - len(' diode'). find_external_schematic이 검색어 끝에 ' diode'를 붙여도 find의 200자 상한을 넘지 않게 한다
    if component_type is not None and (project is not None or len(q) > 194):
        raise HTTPException(422, '다이오드 검색은 194자 이하 참고 자료 조회로만 사용할 수 있습니다.')
    manifest = (_schematic_call(find_external_schematic, q, source_url, connections=project.connections) if project else
                _schematic_call(find_external_schematic, q, source_url, component_type) if component_type else
                _schematic_call(find_external_schematic, q, source_url) if source_url is not None
                else _schematic_call(find_external_schematic, q))
    # [왜] 시트 그림 요청도 같은 프로젝트 · 회로 버전으로 소유 확인과 회로 지문 대조를 다시 하도록 범위를 그림 주소에 싣는다
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
        choices=[ExternalSchematicChoice.model_validate({key: getattr(choice, key)
                                                        for key in ExternalSchematicChoice.model_fields})
                 for choice in manifest.choices],
        circuit_version=circuit_version if project else None,
    )


def _multiple_schematics_requested(question, queries):
    if len(queries) > 1:
        return True
    # [왜] 하나를 고르라는 표현을 '여러 · 모두'보다 먼저 본다. '여러 회로 중 하나만'은 한 개를 달라는 말이다
    if re.search(r'하나만|어느\s*(?:하나|것|회로|제조사|판본|출처)|'
                 r'어떤\s*(?:것|회로|제조사|판본|출처).*(?:고르|선택|맞|인가)|'
                 r'which\s+(?:one|circuit|revision|manufacturer|source)|choose\s+one', question, re.I):
        return False
    return bool(re.search(r'모두|전부|각각|둘\s*다|여러|비교|(?:두|세|[2-9])\s*(?:개|가지|종)|'
                          r'\b(?:all|both|each|multiple|compare|several)\b', question, re.I))


@router.post('/schematics/dialogue', response_model=SchematicDialogueResponse,
             dependencies=[Depends(auth.check_origin)])
def external_schematic_dialogue(body: SchematicDialogueRequest, response: Response,
    user_id: Annotated[int, Depends(auth.current_user_id)], analysis=Depends(analysis_service)):
    """서버가 찾은 후보를 설명한다. 후보 선택과 원본 제공은 기존 GET을 이용한다."""
    from backend.projects.schematic_dialogue import build_dialogue
    from backend.services import llm

    response.headers['Cache-Control'] = 'private, no-store'
    project = _project_circuit(user_id, body.project_id, body.circuit_version, body.thread_id, body.reference_only)
    if body.component_type is not None and (project is not None or any(len(q) > 194 for q in body.queries)):
        raise HTTPException(422, '다이오드 검색은 194자 이하 참고 자료 조회로만 사용할 수 있습니다.')
    queries = list(dict.fromkeys(body.queries))
    # [왜] 외부 검색보다 먼저 LLM 예약 한도를 확인해, 한도가 찬 사용자의 요청은 검색 비용도 쓰지 않고 429로 끝낸다
    try:
        budget = analysis.schematic_dialogue_budget(user_id)
    except llm.EvaluationLimitError:
        raise ApiError(429, '회로도 소개 요청의 예약 한도에 도달했습니다.', code='LIMIT_EXCEEDED') from None
    candidates, failures, seen, errors = [], [], {}, []
    for query in queries:
        try:
            manifest = (_schematic_call(find_external_schematic, query, connections=project.connections) if project else
                        _schematic_call(find_external_schematic, query, None, body.component_type) if body.component_type else
                        _schematic_call(find_external_schematic, query))
        except HTTPException as error:
            errors.append(error)
            failures.append(SchematicSearchFailure(query=query, status_code=error.status_code,
                code=code_for(error.status_code, error), message=error.detail,
                retry_after=(error.headers or {}).get('Retry-After')))
            continue
        choices = manifest.choices or (manifest,)
        for choice in choices:
            values = {name: getattr(choice, name, None) for name in (
                'manufacturer', 'model', 'source_file', 'evidence_grade', 'source_sha256', 'commit',
                'license', 'attribution', 'repository_url', 'license_evidence_url')}
            primary = choice.source_url == manifest.source_url
            if primary:
                for name, value in values.items():
                    if value is None:
                        values[name] = getattr(manifest, name, None)
            key = (choice.source_url, values['source_file'], choice.revision)
            if key in seen:
                seen[key].queries.append(query)
                continue
            params = {'q': query, 'source_url': choice.source_url}
            if project:
                params.update(project_id=body.project_id, circuit_version=body.circuit_version)
                if body.thread_id:
                    params['thread_id'] = str(body.thread_id)
            else:
                params['reference_only'] = 'true'
                if body.component_type:
                    params['component_type'] = body.component_type
            number = len(candidates) + 1
            candidate = SchematicDialogueCandidate(candidate_id=f'C{number}', number=number, queries=[query],
                title=getattr(choice, 'title', None) or manifest.model or manifest.source_file,
                source_url=choice.source_url, source_type=choice.source_type, revision=choice.revision,
                selection_url='/api/external-circuits/schematics?' + urlencode(params), **values)
            seen[key] = candidate
            candidates.append(candidate)
    # [왜] 검색어 일부만 실패하면 찾은 후보와 실패 목록(failures)으로 답하고, 후보가 하나도 없을 때만 첫 오류로 답한다
    if not candidates and errors:
        raise errors[0]
    with llm.evaluation_limits(budget):
        dialogue = build_dialogue(body.question, [candidate.model_dump() for candidate in candidates],
            requested_multiple=_multiple_schematics_requested(body.question, queries),
            chat=llm.schematic_dialogue_chat)
    return SchematicDialogueResponse(queries=queries, count=len(candidates), candidates=candidates,
        dialogue=SchematicDialogue.model_validate(dialogue), failures=failures)


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
