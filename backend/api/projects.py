"""기존 세션과 공통 오류 처리를 사용하는 사용자별 프로젝트 API. 삭제는 같은 UUID의 분석 기록 · checkpoint까지 지운다."""
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from backend import auth
from backend.conversations.repository import InvalidRunState
from backend.projects.models import Project, ProjectSummary
from backend.projects.netlist import InvalidNetlist, MAX_BYTES, NetlistTooLarge, PARSER_VERSION, normalize_netlist
from backend.projects.repository import DEMOS, InvalidProject, ProjectNotFound, ProjectRepository, project_name

router = APIRouter(prefix="/api", tags=["projects"])


class RenameProject(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"name": "전원부 다이오드 교체 검토"}]})
    name: str

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return project_name(value)


class CreateProject(RenameProject):
    # [주의] 이름 바꾸기의 예시를 물려받으면 demo_id가 빠져 422가 된다
    model_config = ConfigDict(json_schema_extra={"examples": [{"demo_id": "attiny85_dev", "name": "ATtiny85 보드 다이오드 검토"}]})
    demo_id: str

    @field_validator("demo_id")
    @classmethod
    def known_demo(cls, value: str) -> str:
        if value not in DEMOS:
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


class DemoCircuit(BaseModel):
    id: str
    name: str


@router.get("/demo-circuits", dependencies=[Depends(auth.current_user_id)], response_model=list[DemoCircuit])
def demo_circuits():
    return [{"id": demo_id, "name": name} for demo_id, name in DEMOS.items()]


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.list_owned(user_id)


@router.post("/projects", status_code=201, response_model=Project, dependencies=[Depends(auth.check_origin)])
def create_project(body: CreateProject, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.create_demo(user_id, body.demo_id, body.name)


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
                            "description": "KiCad 넷리스트(.net, UTF-8, 5 MiB 이하)"},
                   "name": {"type": "string", "description": "프로젝트 이름(앞뒤 공백 제외 1~200자)"}}}}}}}


@router.post("/projects/upload", status_code=201, response_model=Project, dependencies=[Depends(auth.check_origin)], openapi_extra=UPLOAD_BODY)
async def upload_project(request: Request, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
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
            raise HTTPException(400, "업로드 형식이 올바르지 않습니다.")
        items = form.multi_items()
        upload, name = form.get("file"), form.get("name")
        if len(items) != 2 or set(form) != {"file", "name"} or not isinstance(upload, UploadFile) or not isinstance(name, str):
            raise HTTPException(422, "파일과 프로젝트 이름만 입력해 주세요.")
        if not upload.filename or not upload.filename.strip().lower().endswith(".net"):
            raise HTTPException(400, ".net 확장자의 KiCad 넷리스트 파일이 필요합니다.")
        name = project_name(name)
        normalized = normalize_netlist(await upload.read(MAX_BYTES + 1))
        await upload.close()  # 정규화 직후 원본 버퍼를 폐기하고 DB 경계를 지난다.
        return repo.create_upload(user_id, name, connections=normalized.connections,
                                  source_sha256=normalized.source_sha256, parser_version=PARSER_VERSION)
    except (UploadLimit, NetlistTooLarge):
        raise HTTPException(413, "넷리스트는 5 MiB 이하여야 합니다.") from None
    except InvalidProject as exc:
        raise HTTPException(422, str(exc)) from None
    except (MultiPartException, InvalidNetlist):
        raise HTTPException(400, "올바른 UTF-8 KiCad 넷리스트를 올려 주세요.") from None
    finally:
        for upload in parser.uploads:
            await upload.close()


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: int, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.get_owned(user_id, project_id)


@router.patch("/projects/{project_id}", response_model=Project, dependencies=[Depends(auth.check_origin)])
def rename_project(project_id: int, body: RenameProject, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.rename_owned(user_id, project_id, body.name)


def delete_owned_with_checkpoints(user_id, project_id, checkpoint_delete=None):
    """프로젝트와 딸린 것을 바로 지운다: public 업무 행(FK cascade)과 같은 UUID의 분석 thread · checkpoint · 메시지 · 승인 기록 · 분석 사건."""
    # run 생성·재개와 같은 project 행을 잠그고 한 트랜잭션에서 지운다. 분석 기록 삭제가 실패하면 프로젝트도 남는다(11-09 결정, SPEC 8.5)
    # checkpoint_delete(conn, thread_ids)는 시험이 지우는 함수를 바꿔 끼우는 자리다. 기본은 memory_service.delete_analysis_threads
    if checkpoint_delete is None:
        from backend.conversations.memory_service import delete_analysis_threads
        checkpoint_delete = lambda conn, ids: delete_analysis_threads(conn, user_id, ids)
    with auth.connection() as conn:
        if conn.execute('SELECT id FROM projects WHERE id=%s AND user_id=%s FOR UPDATE', (project_id, user_id)).fetchone() is None:
            raise ProjectNotFound
        if conn.execute("SELECT 1 FROM runs r JOIN threads t ON t.id=r.thread_id WHERE t.project_id=%s AND r.status IN ('running','requires_input') LIMIT 1", (project_id,)).fetchone():
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
        raise HTTPException(409, 'run_in_progress') from None
    except ProjectNotFound:
        raise HTTPException(404, '프로젝트를 찾을 수 없습니다.') from None
    except Exception:
        raise HTTPException(503, '프로젝트 서비스를 사용할 수 없습니다.') from None
    return Response(status_code=204)
