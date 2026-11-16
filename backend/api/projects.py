"""기존 세션과 공통 오류 처리를 사용하는 사용자별 프로젝트 API. 삭제는 같은 UUID의 분석 기록 · checkpoint까지 지운다."""
import hashlib
from dataclasses import replace

import psycopg
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from backend import auth
from backend.api.auth import demo_mode
from backend.conversations.repository import LIVE_RUN, InvalidRunState, stale_run_seconds
from backend.projects.models import Project, ProjectSummary
from backend.projects.netlist import InvalidNetlist, InvalidNetlistEncoding, MAX_BYTES, NetlistTooLarge, PARSER_VERSION, normalize_netlist
from backend.projects.repository import DEMOS, InvalidProject, ProjectNotFound, ProjectRepository, project_name
from backend.projects.visuals import load_demo_visuals

router = APIRouter(prefix="/api", tags=["projects"])


class RenameProject(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"name": "전원부 다이오드 교체 검토"}]})
    name: str

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return project_name(value)


class CreateProject(RenameProject):
    model_config = ConfigDict(json_schema_extra={"examples": [{"demo_id": "attiny85_dev", "name": "ATtiny85 보드 다이오드 검토"}]})
    demo_id: str | None = None

    @field_validator("demo_id")
    @classmethod
    def known_demo(cls, value: str | None) -> str | None:
        if value is not None and value not in DEMOS:
            raise ValueError("등록된 데모 회로를 선택해 주세요.")
        return value


def repository():
    try:
        yield ProjectRepository()
    except ProjectNotFound:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다.") from None
    except InvalidProject as exc:
        raise HTTPException(422, str(exc)) from None
    except (psycopg.Error, KeyError, OSError):
        raise HTTPException(503, "프로젝트 서비스를 사용할 수 없습니다.") from None


class DemoSchematic(BaseModel):
    image_url: str
    original_url: str
    source_repo: str
    source_commit: str
    license: str
    license_evidence_url: str
    attribution: str


class DemoCircuitResponse(BaseModel):
    id: str
    name: str
    schematic: DemoSchematic | None


@router.get("/demo-circuits", dependencies=[Depends(auth.current_user_id), Depends(demo_mode)], response_model=list[DemoCircuitResponse])
def demo_circuits(response: Response, q: str | None = Query(default=None, min_length=1),
                  offset: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100)):
    """데모 회로 목록. DEMO_MODE=1에서만(아니면 404, 데모 프로젝트 생성과 같은 규칙). 로그인 필요."""
    visuals = load_demo_visuals()
    items = [{"id": demo_id, "name": name,
             "schematic": visuals[demo_id].model_dump(include=set(DemoSchematic.model_fields)) if demo_id in visuals else None}
            for demo_id, name in DEMOS.items()]
    if q is not None:
        needle = q.casefold()
        items = [item for item in items if needle in item["id"].casefold() or needle in item["name"].casefold()]
    response.headers["Cache-Control"] = "private, max-age=300"
    return items[offset:offset + limit]


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.list_owned(user_id)


@router.post("/projects", status_code=201, response_model=Project, dependencies=[Depends(auth.check_origin)])
def create_project(body: CreateProject, allow_duplicate: bool = False, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    """빈 프로젝트 생성. demo_id를 지정한 복제는 DEMO_MODE=1에서만 허용한다."""
    options = {"allow_duplicate": True} if allow_duplicate else {}
    if body.demo_id is not None:
        demo_mode()
        return repo.create_demo(user_id, body.demo_id, body.name, **options)
    return repo.create_empty(user_id, body.name, **options)


class UploadLimit(MultiPartException):
    """multipart 수신 제한 초과. 프레임워크 오류 원문을 공개하지 않는다."""


class MemoryUploadParser(MultiPartParser):
    # 기본 1 MiB disk rollover를 막고, 이 값 전에 파일/전체 수신 제한으로 거절한다.
    spool_max_size = MAX_BYTES + 2

    def __init__(self, headers, stream):
        super().__init__(headers, stream, max_files=1, max_fields=1, max_part_size=800)
        self.uploads = []
        self.file_bytes = 0
        self.finished = False

    def on_headers_finished(self):
        super().on_headers_finished()
        if self._current_part.file is not None:
            self.uploads.append(self._current_part.file)

    def on_part_data(self, data, start, end):
        if self._current_part.file is not None:
            self.file_bytes += end - start
            if self.file_bytes > MAX_BYTES + 1:
                raise UploadLimit("file limit")
        super().on_part_data(data, start, end)

    def on_end(self):
        self.finished = True
        super().on_end()


# [왜] 본문을 직접 읽어(아래 MemoryUploadParser) FastAPI가 multipart 칸을 모른다. /docs에 파일 · 이름 칸이 보이게 OpenAPI에만 적는다.
#      모양은 FastAPI가 UploadFile · Form에 만드는 스키마와 같고, 수신 상한 · 오류 코드는 아래 처리기가 정한다
UPLOAD_BODY = {"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
    "type": "object", "required": ["file", "name"], "additionalProperties": False,
    "properties": {"file": {"type": "string", "contentMediaType": "application/octet-stream",
                            "description": "KiCad 넷리스트(.net) 또는 하위 시트 없는 회로도(.kicad_sch), UTF-8, 5 MiB 이하"},
                   "name": {"type": "string", "description": "프로젝트 이름(앞뒤 공백 제외 1~200자)"}}}}}}}


@router.post("/projects/upload", status_code=201, response_model=Project, dependencies=[Depends(auth.check_origin)], openapi_extra=UPLOAD_BODY)
async def upload_project(request: Request, allow_duplicate: bool = False, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    normalized, schematic, name = await read_upload(request, with_name=True)
    options = {"allow_duplicate": True} if allow_duplicate else {}
    if schematic is not None:
        options["schematic"] = schematic
    return repo.create_upload(user_id, name, connections=normalized.connections,
                              source_sha256=normalized.source_sha256, parser_version=PARSER_VERSION, **options)


async def read_upload(request: Request, *, with_name: bool):
    # File/Form 의존성은 인증 전에 원본을 디스크에 spool할 수 있으므로 직접 제한한다.
    async def bounded_stream():
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_BYTES + 16_384:
                raise UploadLimit("request limit")
            yield chunk

    parser = MemoryUploadParser(request.headers, bounded_stream())
    try:
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "multipart/form-data":
            raise HTTPException(400, "multipart 파일과 이름이 필요합니다.")
        form = await parser.parse()
        if not parser.finished:
            raise HTTPException(400, "파일을 다시 첨부해 주세요. 업로드 형식이 올바르지 않습니다.")
        items = form.multi_items()
        upload, name = form.get("file"), form.get("name")
        expected = {"file", "name"} if with_name else {"file"}
        if len(items) != len(expected) or set(form) != expected or not isinstance(upload, UploadFile) or (with_name and not isinstance(name, str)):
            raise HTTPException(422, "파일과 프로젝트 이름만 입력해 주세요.")
        extensions = (".net", ".kicad_sch") if with_name else (".net", ".txt", ".kicad_sch")
        if not upload.filename or not upload.filename.strip().lower().endswith(extensions):
            raise HTTPException(400, ".net 넷리스트나 .kicad_sch 회로도 파일이 필요합니다." if with_name else ".net · .txt 넷리스트나 .kicad_sch 회로도 파일이 필요합니다.")
        name = project_name(name) if with_name else None
        raw = await upload.read(MAX_BYTES + 1)
        await upload.close()  # 원본 버퍼를 폐기하고 DB 경계를 지난다. 넷리스트는 정규화한 연결만 남는다.
        if upload.filename.strip().lower().endswith(".kicad_sch"):
            return *(await read_schematic(raw, upload.filename)), name
        return normalize_netlist(raw), None, name
    except (UploadLimit, NetlistTooLarge):
        raise HTTPException(413, "넷리스트·회로도는 5 MiB 이하여야 합니다.") from None
    except InvalidProject as exc:
        raise HTTPException(422, str(exc)) from None
    except InvalidNetlistEncoding:
        raise HTTPException(400, "UTF-8로 다시 저장하거나 KiCad에서 넷리스트(.net)로 다시 내보내 주세요.") from None
    except InvalidNetlist:
        raise HTTPException(400, "KiCad 넷리스트(.net)로 다시 내보내 주세요. PDF·이미지 파일은 사용할 수 없습니다.") from None
    except MultiPartException:
        raise HTTPException(400, "파일을 다시 첨부해 주세요. 업로드 형식이 올바르지 않습니다.") from None
    finally:
        for upload in parser.uploads:
            await upload.close()


SCHEMATIC_HIERARCHY = "하위 시트가 있는 회로도는 아직 지원하지 않아요. 넷리스트(.net)를 함께 올려 주세요."
SCHEMATIC_INVALID = "회로도를 읽지 못했어요. KiCad 6 이상에서 저장한 .kicad_sch인지 확인해 주세요."
SCHEMATIC_RENDERER_DOWN = "회로도 그림 서버에 연결하지 못했어요. 넷리스트(.net)로 올려 주세요."


async def read_schematic(raw: bytes, filename: str):
    """올린 .kicad_sch 한 장을 렌더러로 넷리스트와 그림으로 바꾼다(#52). 넷리스트는 .net 업로드와 같은 정규화를 거친다.

    돌려주는 것: (정규화 회로, (파일 이름, 원문)). source_sha256은 회로도 파일의 해시다.
    [왜] KiCad가 내보낸 넷리스트에는 임시 경로 · 시각이 들어가 같은 회로도도 매번 해시가 달라 409 중복을 못 잡는다.
    """
    from backend.projects.external_schematic import remember_uploaded_sheets
    from backend.projects.schematic import InvalidKicadProject, KicadServiceUnavailable, export_uploaded_kicad
    from backend.projects.schematic_render import HierarchicalSchematic, uploaded_schematic_text
    from backend.projects.schematic_source import ExternalSchematicInvalidSource
    if len(raw) > MAX_BYTES:
        raise NetlistTooLarge("byte limit exceeded")
    try:
        text = uploaded_schematic_text(raw)  # 렌더러에 보내기 전에 (kicad_sch ...) 한 장인지 본다
    except HierarchicalSchematic:
        raise HTTPException(422, SCHEMATIC_HIERARCHY) from None
    except ExternalSchematicInvalidSource:
        raise HTTPException(422, SCHEMATIC_INVALID) from None
    try:
        # [주의] 렌더러 호출(최대 90초)은 동기 httpx라 이벤트 루프를 막지 않게 스레드에서 부른다
        netlist, sheets = await run_in_threadpool(export_uploaded_kicad, text)
        normalized = normalize_netlist(netlist)
    except (InvalidKicadProject, InvalidNetlist):
        raise HTTPException(422, SCHEMATIC_INVALID) from None
    except KicadServiceUnavailable:
        raise HTTPException(503, SCHEMATIC_RENDERER_DOWN) from None
    remember_uploaded_sheets(text, sheets)
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()[-255:]
    return replace(normalized, source_sha256=hashlib.sha256(raw).hexdigest()), (name, text)


class ImportNetlistResponse(BaseModel):
    project: Project
    thread_id: UUID


NETLIST_BODY = {"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
    "type": "object", "required": ["file"], "additionalProperties": False,
    "properties": {"file": {"type": "string", "contentMediaType": "application/octet-stream",
                            "description": "UTF-8 KiCad 넷리스트(.net 또는 .txt) 또는 하위 시트 없는 회로도(.kicad_sch), 5 MiB 이하"}}}}}}}


@router.post("/projects/{project_id}/netlist", status_code=201, response_model=ImportNetlistResponse,
             dependencies=[Depends(auth.check_origin)], openapi_extra=NETLIST_BODY)
async def import_netlist(project_id: int, request: Request, thread_id: UUID | None = None, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    """thread_id: 회로 없이 시작한 그 대화에 회로를 붙여 같은 대화를 이어 간다(조건이 안 맞으면 지금처럼 새 대화, SPEC 4절)."""
    normalized, schematic, _ = await read_upload(request, with_name=False)
    options = {"schematic": schematic} if schematic is not None else {}
    project, thread_id = repo.import_netlist(user_id, project_id, connections=normalized.connections,
                                           source_sha256=normalized.source_sha256, parser_version=PARSER_VERSION, thread_id=thread_id, **options)
    return {"project": project, "thread_id": thread_id}


@router.get("/projects/{project_id}/schematic", response_class=Response,
            responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}})
def uploaded_schematic(project_id: int, circuit_version: int = Query(ge=1), user_id: int = Depends(auth.current_user_id),
                       repo: ProjectRepository = Depends(repository)):
    """그 회로 버전에 올린 회로도(.kicad_sch)의 그림(#52). 소유자만 받고 없으면 404.

    [왜] 외부 회로도처럼 서명한 주소를 쓰지 않는다. 원문이 DB에 있어 요청마다 세션 소유자로 다시 확인하면 된다.
    """
    from backend.projects.external_schematic import uploaded_schematic_sheet
    from backend.projects.schematic import InvalidKicadProject, KicadServiceUnavailable
    source = repo.uploaded_schematic(user_id, project_id, circuit_version)
    try:
        png = uploaded_schematic_sheet(source)
    except InvalidKicadProject:
        raise HTTPException(404, "업로드한 회로도를 그리지 못했습니다.") from None
    except KicadServiceUnavailable:
        raise HTTPException(503, "회로도 그림 서버에 연결하지 못했어요. 잠시 뒤 다시 열어 주세요.") from None
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline"})


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: int, thread_id: UUID | None = None, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.get_owned(user_id, project_id, thread_id) if thread_id is not None else repo.get_owned(user_id, project_id)


@router.patch("/projects/{project_id}", response_model=Project, dependencies=[Depends(auth.check_origin)])
def rename_project(project_id: int, body: RenameProject, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.rename_owned(user_id, project_id, body.name)


def delete_owned_with_checkpoints(user_id, project_id, checkpoint_delete=None):
    """프로젝트와 딸린 것을 바로 지운다: public 업무 행(FK cascade)과 같은 UUID의 분석 thread · checkpoint · 메시지 · 분석 사건."""
    # run 생성·재개와 같은 project 행을 잠그고 한 트랜잭션에서 지운다. 분석 기록 삭제가 실패하면 프로젝트도 남는다(11-09 결정, SPEC 8.5)
    # checkpoint_delete(conn, thread_ids)는 시험이 지우는 함수를 바꿔 끼우는 자리다. 기본은 memory_service.delete_analysis_threads
    if checkpoint_delete is None:
        from backend.conversations.memory_service import delete_analysis_threads
        checkpoint_delete = lambda conn, ids: delete_analysis_threads(conn, user_id, ids)
    with auth.connection() as conn:
        if conn.execute('SELECT id FROM projects WHERE id=%s AND user_id=%s FOR UPDATE', (project_id, user_id)).fetchone() is None:
            raise ProjectNotFound
        # [왜] 멈춘 run(마지막 갱신이 stale 한도보다 오래되고 분석 잠금도 없음)은 막지 않는다. 막으면 인스턴스가 내려간 뒤 프로젝트를 영영 못 지운다(점검 B #3)
        if conn.execute(f"SELECT 1 FROM runs r JOIN threads t ON t.id=r.thread_id WHERE t.project_id=%s AND {LIVE_RUN} LIMIT 1",
                        (project_id, stale_run_seconds())).fetchone():
            raise InvalidRunState
        ids = [str(row[0]) for row in conn.execute('SELECT id FROM threads WHERE project_id=%s', (project_id,)).fetchall()]
        if ids and checkpoint_delete:
            checkpoint_delete(conn, ids)
        conn.execute('DELETE FROM projects WHERE id=%s AND user_id=%s', (project_id, user_id))


@router.delete("/projects/{project_id}", status_code=204, dependencies=[Depends(auth.check_origin)])
def delete_project(project_id: int, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    try:
        delete_owned_with_checkpoints(user_id, project_id)
    except InvalidRunState:
        raise HTTPException(409, '분석이 진행 중인 프로젝트는 삭제할 수 없습니다. 분석이 끝난 뒤 다시 시도해 주세요.') from None
    except ProjectNotFound:
        raise HTTPException(404, '프로젝트를 찾을 수 없습니다.') from None
    except Exception:
        raise HTTPException(503, '프로젝트 서비스를 사용할 수 없습니다.') from None
    return Response(status_code=204)
