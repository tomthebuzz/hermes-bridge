from __future__ import annotations

from pydantic import BaseModel


class CreateTaskRequest(BaseModel):
    title: str
    tenant: str
    body: str = ""
    assignee: str | None = None


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
