"""대화 식별자와 안전한 실행 결과의 내부 형식."""
from typing import Literal
from pydantic import BaseModel, ConfigDict


class SafeResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answer: str = ''


RunStatus = Literal['running', 'requires_input', 'completed', 'refused', 'failed']
