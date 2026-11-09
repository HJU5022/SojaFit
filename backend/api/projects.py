"""기존 세션과 공통 오류 처리를 사용하는 사용자별 프로젝트 API."""
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, field_validator

from backend import auth
from backend.projects.models import Project, ProjectSummary
from backend.projects.repository import DEMOS, InvalidProject, ProjectNotFound, ProjectRepository, project_name

router = APIRouter(prefix="/api", tags=["projects"])


class RenameProject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return project_name(value)


class CreateProject(RenameProject):
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


@router.get("/demo-circuits", dependencies=[Depends(auth.current_user_id)])
def demo_circuits():
    return [{"id": demo_id, "name": name} for demo_id, name in DEMOS.items()]


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.list_owned(user_id)


@router.post("/projects", status_code=201, response_model=Project, dependencies=[Depends(auth.check_origin)])
def create_project(body: CreateProject, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.create_demo(user_id, body.demo_id, body.name)


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: int, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.get_owned(user_id, project_id)


@router.patch("/projects/{project_id}", response_model=Project, dependencies=[Depends(auth.check_origin)])
def rename_project(project_id: int, body: RenameProject, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    return repo.rename_owned(user_id, project_id, body.name)


@router.delete("/projects/{project_id}", status_code=204, dependencies=[Depends(auth.check_origin)])
def delete_project(project_id: int, user_id: int = Depends(auth.current_user_id), repo: ProjectRepository = Depends(repository)):
    repo.delete_owned(user_id, project_id)
    return Response(status_code=204)
