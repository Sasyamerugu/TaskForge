from pydantic import BaseModel, Field
from typing import Any, Literal


class JobCreate(BaseModel):
    task_type: str = Field(min_length=1)
    input_data: dict[str, Any]
    priority: Literal["low", "medium", "high"] = "medium"


class JobResponse(BaseModel):
    id: str
    task_type: str
    status: str
    result: str | None = None
    error: str | None = None
    retry_count: int

    model_config = {
        "from_attributes": True
    }
    priority: str
    effective_priority: str