"""프로젝트 API에 공개하는 메타데이터와 정규화 회로 DTO."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, computed_field


class ProjectSummary(BaseModel):
    id: int
    name: str
    source_kind: Literal["demo", "upload"]
    demo_id: str | None
    created_at: datetime
    updated_at: datetime
    circuit_version: int = 0

    @computed_field
    @property
    def has_circuit(self) -> bool:
        """회로가 있는지(빈 프로젝트는 v0, 데모 복제·업로드는 v1부터). 사이드바가 회로 없는 대화를 따로 모은다(#31)."""
        return self.circuit_version > 0


class Project(ProjectSummary):
    connections: dict
    schematic_file: str | None = None
    """이 회로 버전에 올린 회로도(.kicad_sch) 파일 이름. 없으면 None이고 화면은 웹 검색으로 원본 회로도를 찾는다(#52)."""
