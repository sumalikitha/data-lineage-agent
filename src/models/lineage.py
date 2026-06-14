from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class LineageNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    table_name: str
    columns: list[str] = Field(default_factory=list)
    row_count: Optional[int] = None
    description: Optional[str] = None


class LineageEdge(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_table: str
    target_table: str
    relationship_type: str  # "foreign_key" | "implicit_join"
    join_columns: list[str] = Field(default_factory=list)


class LineageReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    status: RunStatus = RunStatus.pending
    nodes: list[LineageNode] = Field(default_factory=list)
    edges: list[LineageEdge] = Field(default_factory=list)
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class AnalyzeRequest(BaseModel):
    notes: Optional[str] = None


class AnalyzeResponse(BaseModel):
    run_id: str
    status: RunStatus
    message: str
