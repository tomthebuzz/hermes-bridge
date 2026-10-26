from __future__ import annotations

from pydantic import BaseModel

from ...core.sanitize import SanitizedModel


class CreateTaskRequest(SanitizedModel):
    title: str
    tenant: str
    body: str = ""
    assignee: str | None = None
    status: str = "running"
    priority: int = 0


class EditTaskRequest(SanitizedModel):
    title: str | None = None
    body: str | None = None
    priority: int | None = None


class TransitionRequest(SanitizedModel):
    status: str
    reason: str = "Moved from Team Portal"
    current_status: str | None = None
    author: str | None = None


class AssignRequest(SanitizedModel):
    assignee: str


class CommentRequest(SanitizedModel):
    text: str
    author: str | None = None


class ReviewRequest(SanitizedModel):
    note: str = ""
    author: str | None = None


class RejectRequest(SanitizedModel):
    reason: str
    author: str | None = None


class PublishForReviewRequest(SanitizedModel):
    summary: str = ""


class BridgeResult(BaseModel):
    ok: bool
    detail: str = ""
    # True when hidden characters were removed from the request's text.
    sanitized: bool = False
