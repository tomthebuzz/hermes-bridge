from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from ...core.sanitize import SanitizedModel


class CreateTaskRequest(SanitizedModel):
    title: str
    tenant: str
    body: str = ""
    assignee: str | None = None
    status: str = "running"
    priority: int = 0
    # skills force-loaded into the worker (hermes kanban create --skill), e.g. team-review
    skills: list[str] = Field(default_factory=list)
    created_by: str | None = Field(default=None, pattern=r"^[A-Za-z0-9 ._-]{1,60}$")

    @field_validator("skills")
    @classmethod
    def _skill_names(cls, v: list[str]) -> list[str]:
        for name in v:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", name):
                raise ValueError(f"skill name '{name}' must be lowercase letters, digits and dashes")
        return v


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
