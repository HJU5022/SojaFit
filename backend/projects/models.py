"""프로젝트 API에 공개하는 메타데이터와 정규화 회로 DTO."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ProjectSummary(BaseModel):
    id: int
    name: str
    source_kind: Literal["demo", "upload"]
    demo_id: str | None
    created_at: datetime
    updated_at: datetime
    circuit_version: int = 0


class Project(ProjectSummary):
    connections: dict
