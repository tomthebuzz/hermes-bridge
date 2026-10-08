from __future__ import annotations

from pydantic import BaseModel


class CreateTaskRequest(BaseModel):
    title: str
    tenant: str
    body: str = ""
    assignee: str | None = None
    status: str = "running"
    priority: int = 0


class EditTaskRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    priority: int | None = None


class TransitionRequest(BaseModel):
    status: str
    reason: str = "Moved from Team Portal"
    current_status: str | None = None


class AssignRequest(BaseModel):
    assignee: str


class CommentRequest(BaseModel):
    text: str
    author: str | None = None


class ReviewRequest(BaseModel):
    note: str = ""


class RejectRequest(BaseModel):
    reason: str


class PublishForReviewRequest(BaseModel):
    summary: str = ""


class BridgeResult(BaseModel):
    ok: bool
    detail: str = ""
